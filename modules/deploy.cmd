@echo off
TITLE Automated Network Deployment
color 0A

echo ==========================================
echo    Starting Automated Windows Deployment
echo ==========================================

echo [1/4] Preparing disk partitions...
echo select disk 0 > %TEMP% \part.txt
echo clean >> %TEMP% \part.txt
echo convert gpt >> %TEMP% \part.txt
echo create partition efi size=100 >> %TEMP% \part.txt
echo format quick fs=fat32 label="System" >> %TEMP% \part.txt
echo assign letter=S >> %TEMP% \part.txt
echo create partition msr size=16 >> %TEMP% \part.txt
echo create partition primary >> %TEMP% \part.txt
echo format quick fs=ntfs label="Windows" >> %TEMP% \part.txt
echo assign letter=W >> %TEMP% \part.txt
diskpart /s %TEMP% \part.txt

echo [2/4] Downloading install.wim from server...
curl -o X:\install.wim http://192.168.0.120/winpe/sources/install.wim

echo [3/4] Applying Windows Image...
dism /apply-image /imagefile:X:\install.wim /index:1 /applydir:W:\

echo [4/4] Generating UEFI boot files...
bcdboot W:\Windows /s S: /f UEFI

echo ==========================================
echo    Deployment Complete! Rebooting...
echo ==========================================
pause
wpeutil reboot