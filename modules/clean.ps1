# Requires -RunAsAdministrator

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

# Define the root directory (handles execution from modules/ or root)
if ($ScriptDir -match "modules$") {
    $RootDir = Split-Path -Parent $ScriptDir
} else {
    $RootDir = $ScriptDir
}

$WinpeDir         = Join-Path $RootDir "winpe"
$WinpeSourcesDir   = Join-Path $WinpeDir "sources"
$CustomConfigsDir  = Join-Path $RootDir "customizable_configs"
$ConfigsDir        = Join-Path $RootDir "configs"
$ScriptsDir        = Join-Path $RootDir "scripts"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Cleaning Project Staging & Output Folders " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Entirely clear the winpe folder contents if it exists
if (Test-Path $WinpeDir) {
    Write-Host "[*] Cleaning existing winpe folder contents..." -ForegroundColor Yellow
    Remove-Item -Path "$WinpeDir\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Winpe folder contents cleared successfully." -ForegroundColor Green
}

# Entirely clear the scripts folder contents if it exists
if (Test-Path $ScriptsDir) {
    Write-Host "[*] Cleaning existing scripts folder contents..." -ForegroundColor Yellow
    Remove-Item -Path "$ScriptsDir\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [+] Scripts folder contents cleared successfully." -ForegroundColor Green
}

# Create missing directories matching the tree
@($WinpeDir, $WinpeSourcesDir, $CustomConfigsDir, $ConfigsDir, $ScriptsDir) | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

Write-Host "`n[SUCCESS] Directories cleaned and layout verified!" -ForegroundColor Green