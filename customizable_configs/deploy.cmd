@echo off
title WinPE Automated Windows Deployment
cls

echo Starting Automated Windows Deployment...
echo Initializing network drivers and DHCP...
wpeinit
wpeutil waitForNetwork

:: 1. Extract MAC address natively
set "MAC=UNKNOWN"
for /f "tokens=2 delims=:" %%A in ('ipconfig /all ^| find /i "Physical Address"') do (
    set "MAC=%%A"
    goto :got_mac
)
:got_mac
set "MAC=%MAC: =%"
set "MAC=%MAC:-=%"

echo [*] Client MAC Address: %MAC%

:: 2. Generate raw disk details using diskpart
echo [*] Gathering disk details natively...
echo list disk > X:\dp.txt
echo list volume >> X:\dp.txt
diskpart /s X:\dp.txt > X:\diskinfo.txt

:: 3. Upload text report to server (passing MAC as a header)
echo [*] Uploading system inventory to http://__SERVER_IP__/api/inventory ...
curl.exe -s -X POST -H "X-Client-MAC: %MAC%" --data-binary @X:\diskinfo.txt http://__SERVER_IP__/api/inventory

:: 4. Poll server for generated execution script
echo [*] Waiting for operator configuration from server console...
:fetch_loop
ping 127.0.0.1 -n 4 > nul
curl.exe -s -f http://__SERVER_IP__/scripts/run_%MAC%.cmd -o X:\run.cmd
if not exist X:\run.cmd goto :fetch_loop

:: 5. Execute generated deployment tasks
echo [+] Configuration received! Executing deployment...
call X:\run.cmd