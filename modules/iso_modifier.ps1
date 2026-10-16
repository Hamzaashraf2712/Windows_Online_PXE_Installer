# Requires -RunAsAdministrator

$ScriptDir        =$PSScriptRoot
if (-not $ScriptDir) {$ScriptDir = (Get-Location).Path }

$RootDir = Split-Path -Parent $ScriptDir

$WinpeDir          = Join-Path $RootDir "\winpe"
$WinpeSourcesDir   = Join-Path $WinpeDir "\sources"
$CustomConfigsDir  = Join-Path $ScriptDir "..\customizable_configs"
$MountDir          = Join-Path $env:TEMP "pxe_wim_mount"


Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " 2/2: Extract ISO OS Files & Apply Gamechanger Payload " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Force GUI file picker window at startup
Add-Type -AssemblyName System.Windows.Forms
$FilePicker = New-Object System.Windows.Forms.OpenFileDialog
$FilePicker.Filter = "Windows ISO Files (*.iso)|*.iso|All Files (*.*)|*.*"
$FilePicker.Title = "Select Windows ISO File"
$FilePicker.InitialDirectory =$ScriptDir

if ($FilePicker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "[-] No ISO selected. Operations canceled." -ForegroundColor Red
    return
}

$IsoPath =$FilePicker.FileName
Write-Host "[*] Selected ISO: $IsoPath" -ForegroundColor Green

# Ensure DISM state is completely clean of prior broken mounts
Write-Host "[*] Cleaning up stale DISM mount points..." -ForegroundColor Yellow
dism.exe /Unmount-Image "/MountDir:$MountDir" /Discard 2>$null | Out-Null
dism.exe /Cleanup-Mountpoints 2>$null | Out-Null
dism.exe /Cleanup-Wim 2>$null | Out-Null

if (Test-Path $MountDir) { 
    Remove-Item -Path $MountDir -Recurse -Force -ErrorAction SilentlyContinue 
}
New-Item -ItemType Directory -Path $MountDir -Force | Out-Null
if (-not (Test-Path $WinpeSourcesDir)) { New-Item -ItemType Directory -Path$WinpeSourcesDir -Force | Out-Null }

Write-Host "[*] Mounting ISO..." -ForegroundColor Cyan
$MountedDisk = Mount-DiskImage -ImagePath $IsoPath -PassThru
Start-Sleep -Seconds 2
$DriveLetter = ($MountedDisk | Get-Volume).DriveLetter + ":"

if (-not $DriveLetter -or$DriveLetter -eq ":") {
    Write-Error "[-] Failed to resolve drive letter for mounted ISO."
    return
}

Write-Host "[*] ISO mounted on $DriveLetter" -ForegroundColor Green

# 1. Extract Boot WIM
$WimSrc = if (Test-Path "$DriveLetter\sources\boot.wim") { "$DriveLetter\sources\boot.wim" } else { "$DriveLetter\boot.wim" }
if (Test-Path $WimSrc) {
    Write-Host "[*] Extracting boot.wim..." -ForegroundColor Yellow
    Copy-Item -Path $WimSrc -Destination (Join-Path $WinpeSourcesDir "boot.wim") -Force
} else {
    Write-Error "[-] boot.wim not found in ISO."
    Dismount-DiskImage -ImagePath $IsoPath | Out-Null
    return
}

# 2. Extract OS Image (install.wim, install.esd, or install.swm)
$OsImage = Get-ChildItem -Path "$DriveLetter\sources" -Include "install.wim", "install.esd", "install.swm" -Recurse | Select-Object -First 1
if ($OsImage) {
    Write-Host "`n[*] Scanning OS Image ($($OsImage.Name)) for Windows editions..." -ForegroundColor Yellow
    
    $WimInfo = dism.exe /Get-WimInfo "/WimFile:$($OsImage.FullName)"
    $Editions = @{}
    $CurrentIndex = $null

    foreach ($line in $WimInfo) {
        if ($line -match "Index : (\d+)") {
            $CurrentIndex = $matches[1]
        }
        elseif ($line -match "Name : (.+)" -and $CurrentIndex) {
            $Editions[$CurrentIndex] = $matches[1].Trim()
            $CurrentIndex = $null
        }
    }

    if ($Editions.Count -gt 0) {
        Write-Host "`n--- Available Windows Editions ---" -ForegroundColor Cyan
        foreach ($key in ($Editions.Keys | Sort-Object {[int]$_})) {
            Write-Host " [$key]$($Editions[$key])" -ForegroundColor White
        }

        $Choice = Read-Host "`nEnter the Index number to lock in (or press Enter to skip and copy all editions)"

        if (-not [string]::IsNullOrWhiteSpace($Choice) -and $Editions.ContainsKey($Choice)) {
            $DestWim = Join-Path $WinpeSourcesDir "install.wim"
            if (Test-Path $DestWim) { Remove-Item $DestWim -Force }

            Write-Host "`n[*] Isolating '$($Editions[$Choice])' (Index$Choice)..." -ForegroundColor Yellow
            dism.exe /Export-Image "/SourceImageFile:$($OsImage.FullName)" /SourceIndex:$Choice "/DestinationImageFile:$DestWim" /CheckIntegrity
            Write-Host "  [+] Edition successfully isolated to winpe\sources\install.wim" -ForegroundColor Green
        } else {
            if (-not [string]::IsNullOrWhiteSpace($Choice)) {
                Write-Host "  [-] Invalid choice. Defaulting to full copy..." -ForegroundColor Red
            }
            Write-Host "`n[*] Copying full OS Image..." -ForegroundColor Yellow
            Copy-Item -Path $OsImage.FullName -Destination (Join-Path $WinpeSourcesDir $OsImage.Name) -Force
            Write-Host "  [+] OS file saved to winpe\sources\$($OsImage.Name)" -ForegroundColor Green
        }
    } else {
        Write-Host "[*] Could not parse editions. Copying full OS Image..." -ForegroundColor Yellow
        Copy-Item -Path $OsImage.FullName -Destination (Join-Path $WinpeSourcesDir $OsImage.Name) -Force
        Write-Host "  [+] OS file saved to winpe\sources\$($OsImage.Name)" -ForegroundColor Green
    }
} else {
    Write-Host "  [-] Warning: No install.wim/esd/swm found in ISO." -ForegroundColor Red
}

# 3. Extract Boot Environment Files (BCD and boot.sdi)
$BcdSrc = if (Test-Path "$DriveLetter\efi\microsoft\boot\bcd") { "$DriveLetter\efi\microsoft\boot\bcd" } else { "$DriveLetter\boot\bcd" }
$SdiSrc = "$DriveLetter\boot\boot.sdi"

if (Test-Path $BcdSrc) { Copy-Item -Path $BcdSrc -Destination (Join-Path $WinpeSourcesDir "bcd") -Force }
if (Test-Path $SdiSrc) { Copy-Item -Path $SdiSrc -Destination (Join-Path $WinpeSourcesDir "boot.sdi") -Force }

# 4. Safely Unmount ISO
Write-Host "`n[*] Unmounting ISO..." -ForegroundColor Cyan
Dismount-DiskImage -ImagePath $IsoPath | Out-Null

# Clear Read-Only flags
Get-ChildItem -Path $WinpeSourcesDir -Recurse | Set-ItemProperty -Name IsReadOnly -Value $false

# 5. Patch boot.wim with Gamechanger Configuration
$TargetWim = Join-Path $WinpeSourcesDir "boot.wim"

# Determine target index (index 2 for standard Setup ISOs, index 1 if only 1 exists)
$BootWimInfo = dism.exe /Get-WimInfo "/WimFile:$TargetWim"
$TargetIndex = 1
if ($BootWimInfo -match "Index : 2") {
    $TargetIndex = 2
}

Write-Host "`n[*] Injecting Gamechanger setup into $TargetWim (Index $TargetIndex)..." -ForegroundColor Yellow

dism.exe /Mount-Image "/ImageFile:$TargetWim" "/Index:$TargetIndex" "/MountDir:$MountDir"

if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$MountDir\Windows\System32")) {
    Write-Error "[-] DISM failed to mount $TargetWim. Check administrative rights or locked files."
    return
}

# Copy customizable configs into mounted WIM root
$DeployCmdSrc = Join-Path $CustomConfigsDir "deploy.cmd"
$UnattendSrc  = Join-Path $CustomConfigsDir "autounattend.xml"

if (Test-Path $DeployCmdSrc) {
    Copy-Item -Path $DeployCmdSrc -Destination "$MountDir\deploy.cmd" -Force
    Write-Host "  [+] Injected customizable_configs\deploy.cmd -> X:\deploy.cmd" -ForegroundColor Green
}

if (Test-Path $UnattendSrc) {
    Copy-Item -Path $UnattendSrc -Destination "$MountDir\autounattend.xml" -Force
    Write-Host "  [+] Injected customizable_configs\autounattend.xml -> X:\autounattend.xml" -ForegroundColor Green
}

$HostCurl = "$env:SystemRoot\System32\curl.exe"
if (Test-Path $HostCurl) {
    Copy-Item -Path $HostCurl -Destination "$MountDir\Windows\System32\curl.exe" -Force
    Write-Host "  [+] Injected curl.exe -> WinPE System32\curl.exe" -ForegroundColor Green
} else {
    Write-Host "  [-] Warning: curl.exe not found on host System32." -ForegroundColor Yellow
}

# Configure startnet.cmd and winpeshl.ini
Set-Content -Path "$MountDir\Windows\System32\startnet.cmd" -Value "wpeinit`r`ncmd.exe /k X:\deploy.cmd" -Encoding Ascii
Set-Content -Path "$MountDir\Windows\System32\winpeshl.ini" -Value "[LaunchApps]`r`n%SYSTEMDRIVE%\deploy.cmd" -Encoding Ascii

# Apply offline registry execution hook
$HivePath = "$MountDir\Windows\System32\config\SYSTEM"
if (Test-Path $HivePath) {
    reg load "HKLM\OFFLINE_WINPE" "$HivePath" | Out-Null
    reg add "HKLM\OFFLINE_WINPE\Setup" /v CmdLine /t REG_SZ /d "cmd.exe /k X:\deploy.cmd" /f | Out-Null
    reg add "HKLM\OFFLINE_WINPE\Setup" /v SetupType /t REG_DWORD /d 1 /f | Out-Null

    [gc]::Collect()
    Start-Sleep -Seconds 1
    reg unload "HKLM\OFFLINE_WINPE" | Out-Null
} else {
    Write-Host "  [-] Warning: SYSTEM registry hive not found in mounted WIM." -ForegroundColor Red
}

# Commit and clean up
Write-Host "[*] Committing changes to boot.wim..." -ForegroundColor Cyan
dism.exe /Unmount-Image "/MountDir:$MountDir" /Commit

if (Test-Path $MountDir) { 
    Remove-Item -Path $MountDir -Recurse -Force -ErrorAction SilentlyContinue 
}

Write-Host "`n[SUCCESS] Process complete! OS files and patched boot.wim are staged in winpe\sources\" -ForegroundColor Green