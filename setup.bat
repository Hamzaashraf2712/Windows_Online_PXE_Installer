@echo off
setlocal
color 0B

echo ==========================================
echo    Checking System Prerequisites...
echo ==========================================

set "PY_VERSION=3.11.5"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"
set "PY_INSTALLER=%TEMP%\python_installer.exe"

:: A real interpreter is needed. The Microsoft Store alias can pass a
:: plain "python --version" check without Python actually being installed.
python -c "import sys" >nul 2>&1
if not errorlevel 1 goto :run

echo [!] Python not found.
echo [*] Downloading Python %PY_VERSION%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing"
if errorlevel 1 goto :dlfail
if not exist "%PY_INSTALLER%" goto :dlfail

:: Detect admin rights. All-users install needs elevation; otherwise install per-user.
net session >nul 2>&1
if not errorlevel 1 (set "SCOPE=1") else (set "SCOPE=0")

echo [*] Installing Python (InstallAllUsers=%SCOPE%)...
"%PY_INSTALLER%" /quiet InstallAllUsers=%SCOPE% PrependPath=1 Include_test=0 Include_doc=0
set "INSTALL_RC=%errorlevel%"
del /f /q "%PY_INSTALLER%" >nul 2>&1

if not "%INSTALL_RC%"=="0" (
    echo [ERROR] Python installer failed with code %INSTALL_RC%.
    pause
    exit /b 1
)

echo [+] Python installed.
echo [!] Close this window and run again so PATH refreshes.
pause
exit /b 0

:dlfail
echo [ERROR] Failed to download the Python installer. Check your network connection.
pause
exit /b 1

:run
echo [+] Python environment verified. Launching Orchestrator...
python "%~dp0main.py"
set "APP_RC=%errorlevel%"
if not "%APP_RC%"=="0" echo [ERROR] main.py exited with code %APP_RC%.
pause
exit /b %APP_RC%