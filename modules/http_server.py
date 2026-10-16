import http.server
import socketserver
import threading
import json
from pathlib import Path
from config import ROOT_DIR, WINPE_DIR

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    def translate_path(self, path):
        clean = path.split('?')[0].split('#')[0].strip('/')
        
        pe_path = WINPE_DIR / clean
        if pe_path.exists():
            return str(pe_path)
        
        root_path = ROOT_DIR / clean
        if root_path.exists():
            return str(root_path)

        req_name = Path(clean).name.lower()
        if req_name == "bcd":
            req_name = "BCD"

        for p in WINPE_DIR.rglob("*"):
            if p.is_file() and p.name.lower() == req_name.lower():
                return str(p)

        for p in ROOT_DIR.rglob("*"):
            if p.is_file() and p.name.lower() == req_name.lower():
                return str(p)

        return super().translate_path(path)

    def do_POST(self):
        if self.path == '/api/inventory':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            raw_mac = self.headers.get('X-Client-MAC', 'UNKNOWN').strip()
            clean_mac = raw_mac.replace(':', '').replace('-', '').upper()
            client_ip = self.client_address[0]

            print("\n" + "="*70)
            print(f" [*] ACTION REQUIRED: WinPE Client {client_ip} ({raw_mac})")
            print("="*70)

            disk_details = post_data.decode('utf-8', errors='ignore').strip()
            if disk_details:
                print(disk_details)
            else:
                print(" [!] No disk details received.")

            # --- SERVER-SIDE OPTIONS MENU ---
            print("\nSelect Deployment Strategy:")
            print(" [1] Clean Wipe Target Disk (Full OS Disk)")
            print(" [2] Format Existing Partition & Install OS (Content-Aware Detection)")
            print(" [3] Split Target Disk (Custom OS Size + Data Partition)")

            choice = input("\nEnter Choice [1-3] [Default 1]: ").strip()
            if choice not in ["1", "2", "3"]:
                choice = "1"

            target_disk = input(" Target Disk Number to operate on [Default 0]: ").strip()
            if not target_disk.isdigit():
                target_disk = "0"

            part_script_logic = ""

            if choice == "2":
                part_script_logic = f"""
echo [*] Attempting to mount existing EFI System Partition...
mountvol S: /S >nul
if not exist S:\\ (
    echo [!] WARNING: Could not mount EFI partition automatically.
) else (
    echo [+] EFI Partition successfully mounted to S:. Formatting...
    format S: /FS:FAT32 /Q /Y >nul
)

echo [*] Scanning local drives for existing Windows installation...
set OS_DRIVE=
for %%D in (C D E F G H I J K L M N O P Q R T U V W Y Z) do (
    if exist "%%D:\\Windows\\System32\\ntoskrnl.exe" (
        set OS_DRIVE=%%D:
        goto found_os
    )
)

echo [!] No existing \\Windows folder found. The OS partition may be empty or wiped.
echo ---------------------------------------------------
echo Current Volumes available on the system:
echo list volume | diskpart
echo ---------------------------------------------------
set /p manual_letter="Enter the DRIVE LETTER to format and install Windows on (e.g., C, D, E): "
if "%manual_letter%"=="" (
    echo [ERROR] No drive letter specified. Aborting.
    pause
    exit /b 1
)
set OS_DRIVE=%manual_letter%:

:found_os
echo [+] OS Drive designated as: %OS_DRIVE%
echo [+] Formatting %OS_DRIVE% to prepare for fresh image...
format %OS_DRIVE% /FS:NTFS /Q /Y /V:Windows >nul
"""

            elif choice == "3":
                # Option 3: Split Target Disk (Custom OS Size + Data Partition)
                os_gb = input(" Enter Windows OS Partition Size in GB (e.g. 60, 100) [Default 120]: ").strip()
                if not os_gb.isdigit(): os_gb = "120"
                os_mb = int(os_gb) * 1024
                
                create_data = input(" Create Data partition with remaining space? (Y/N) [Default Y]: ").strip().upper()
                if create_data == "": create_data = "Y"

                dp_cmds = [
                    f"select disk {target_disk}",
                    "clean",
                    "convert gpt",
                    "create partition efi size=100",
                    'format quick fs=fat32 label="System"',
                    "assign letter=S",
                    "create partition msr size=16",
                    f"create partition primary size={os_mb}",
                    'format quick fs=ntfs label="Windows"',
                    "assign letter=C"
                ]
                if create_data != "N":
                    dp_cmds.extend([
                        "create partition primary",
                        'format quick fs=ntfs label="Data"',
                        "assign letter=D"
                    ])
                
                dp_filename = f"diskpart_{clean_mac}.txt"
                (ROOT_DIR / "scripts" / dp_filename).write_text("\n".join(dp_cmds) + "\n", encoding='utf-8')

                part_script_logic = f"""
echo [*] Partitioning Disk {target_disk} into OS and Data drives...
curl.exe -f -s -o X:\\dp.txt http://192.168.0.120/scripts/{dp_filename}
diskpart /s X:\\dp.txt >nul
set OS_DRIVE=C:
"""

            else:
                # Option 1: Clean Wipe
                dp_cmds = [
                    f"select disk {target_disk}",
                    "clean",
                    "convert gpt",
                    "create partition efi size=100",
                    'format quick fs=fat32 label="System"',
                    "assign letter=S",
                    "create partition msr size=16",
                    "create partition primary",
                    'format quick fs=ntfs label="Windows"',
                    "assign letter=C"
                ]
                dp_filename = f"diskpart_{clean_mac}.txt"
                (ROOT_DIR / "scripts" / dp_filename).write_text("\n".join(dp_cmds) + "\n", encoding='utf-8')

                part_script_logic = f"""
echo [*] Executing Clean Wipe and Partitioning on Disk {target_disk}...
curl.exe -f -s -o X:\\dp.txt http://192.168.0.120/scripts/{dp_filename}
diskpart /s X:\\dp.txt >nul
set OS_DRIVE=C:
"""

            scripts_dir = ROOT_DIR / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_filename = f"run_{clean_mac}.cmd"
            script_path = scripts_dir / script_filename

            full_script = f"""@echo off
setlocal EnableDelayedExpansion
color 0B
echo ===================================================
echo  EXECUTING AUTOMATED DEPLOYMENT FOR MAC: {raw_mac}
echo ===================================================

{part_script_logic}

echo.
echo [*] Downloading Windows OS image from server...
if exist %OS_DRIVE%\\install.wim del /f /q %OS_DRIVE%\\install.wim
if exist %OS_DRIVE%\\install.esd del /f /q %OS_DRIVE%\\install.esd

curl.exe -f -# -o %OS_DRIVE%\\install.wim http://192.168.0.120/winpe/sources/install.wim
if not exist %OS_DRIVE%\\install.wim (
    echo [!] install.wim not found, trying install.esd...
    curl.exe -f -# -o %OS_DRIVE%\\install.esd http://192.168.0.120/winpe/sources/install.esd
)

if not exist %OS_DRIVE%\\install.wim if not exist %OS_DRIVE%\\install.esd (
    echo [ERROR] OS Image download failed from server!
    pause
    exit /b 1
)

echo.
echo [*] Applying Windows Image to %OS_DRIVE%\\...
if exist %OS_DRIVE%\\install.wim (
    dism /Apply-Image /ImageFile:%OS_DRIVE%\\install.wim /Index:1 /ApplyDir:%OS_DRIVE%\\ /Compact
    del /f /q %OS_DRIVE%\\install.wim
) else (
    dism /Apply-Image /ImageFile:%OS_DRIVE%\\install.esd /Index:1 /ApplyDir:%OS_DRIVE%\\ /Compact
    del /f /q %OS_DRIVE%\\install.esd
)

if not exist %OS_DRIVE%\\Windows\\System32\\ntoskrnl.exe (
    echo [ERROR] DISM failed to apply OS image to drive %OS_DRIVE%\\!
    pause
    exit /b 1
)

echo.
echo [*] Injecting autounattend.xml...
if not exist %OS_DRIVE%\\Windows\\Panther mkdir %OS_DRIVE%\\Windows\\Panther
if not exist %OS_DRIVE%\\Windows\\System32\\Sysprep mkdir %OS_DRIVE%\\Windows\\System32\\Sysprep
curl.exe -f -s -o %OS_DRIVE%\\unattend.xml http://192.168.0.120/customizable_configs/unattend.xml
if exist %OS_DRIVE%\\unattend.xml (
    copy /y %OS_DRIVE%\\unattend.xml %OS_DRIVE%\\Windows\\Panther\\unattend.xml >nul
    copy /y %OS_DRIVE%\\unattend.xml %OS_DRIVE%\\Windows\\System32\\Sysprep\\unattend.xml >nul
    echo [+] Unattend.xml injected successfully.
)

echo.
echo [*] Generating UEFI bootloader on S:\\...
bcdboot %OS_DRIVE%\\Windows /s S: /f UEFI
if errorlevel 1 (
    echo [!] UEFI Bootloader warning, trying fallback /f ALL...
    bcdboot %OS_DRIVE%\\Windows /s S: /f ALL
)

echo ===================================================
echo  SUCCESS! Deployment completed for MAC: {raw_mac}
echo  Rebooting system in 5 seconds...
echo ===================================================
timeout /t 5 /nobreak
wpeutil reboot
"""
            script_path.write_text(full_script, encoding='utf-8')
            print(f"\n[+] Deployment script created: {script_path}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "generated"}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} -> {format % args}")

def start_http_server(port=80):
    def run():
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("0.0.0.0", port), CustomHTTPRequestHandler) as httpd:
            print(f"[HTTP] Deployment File Server running on TCP port {port}...")
            httpd.serve_forever()

    threading.Thread(target=run, daemon=True).start()