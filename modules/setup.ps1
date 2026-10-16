# Requires -RunAsAdministrator

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

# Define the root directory (parent of modules/)
if ($ScriptDir -match "modules$") {
    $RootDir = Split-Path -Parent $ScriptDir
} else {
    $RootDir = $ScriptDir
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " 1/2: Preparing Project Tree & Downloading Binaries " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Call clean.ps1 to handle directory purging and tree verification
$CleanScriptPath = Join-Path $PSScriptRoot "clean.ps1"
if (Test-Path $CleanScriptPath) {
    & $CleanScriptPath
} else {
    Write-Host "[-] Warning: clean.ps1 not found, skipping pre-clean." -ForegroundColor Yellow
}

$WinpeDir         = Join-Path $RootDir "winpe"
$WinpeSourcesDir   = Join-Path $WinpeDir "sources"

# Reliable binary source locations
$downloads = @{
    "https://raw.githubusercontent.com/FOGProject/fogproject/master/packages/tftp/ipxe.efi"  = (Join-Path $WinpeDir "ipxe.efi")
    "https://github.com/ipxe/wimboot/releases/latest/download/wimboot"                          = (Join-Path $WinpeDir "wimboot")
}

$userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

foreach ($url in $downloads.Keys) {
    $target = $downloads[$url]
    $fileName = Split-Path $target -Leaf
    Write-Host "[*] Downloading $fileName..." -ForegroundColor Yellow
    
    try {
        Invoke-WebRequest -Uri $url -OutFile $target -UserAgent $userAgent -UseBasicParsing
        if ((Test-Path $target) -and ((Get-Item $target).Length -gt 0)) {
            $sizeKb = [math]::Round(((Get-Item $target).Length / 1KB), 2)
            Write-Host "  [+] Successfully saved $fileName ($sizeKb KB) to $target" -ForegroundColor Green
        } else {
            throw "Downloaded file is empty."
        }
    } catch {
        Write-Host "  [-] Download failed for $fileName : $($_.Exception.Message)" -ForegroundColor Red
    }
}

