import os
import sys
import ctypes
import subprocess
import glob
import xml.etree.ElementTree as ET
from pathlib import Path

# Project Root Directory
RootMDir = os.path.dirname(os.path.abspath(__file__))

# 1. Self-elevate to Administrator privileges if not already running as admin
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    script = os.path.abspath(sys.argv[0])
    # Properly wrap script path in quotes to handle spaces in folder names
    params = f'"{script}"' + (' ' + ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else '')
    
    # Request elevation via ShellExecuteW
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, RootMDir, 1)
    if int(ret) <= 32:
        print(f"[-] Elevation failed or cancelled by user (Error code: {ret}).")
        input("Press Enter to exit...")
    sys.exit()

# Project Root Directory
RootMDir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = Path(__file__).resolve().parent

print("========================================================")
print(" PXE Orchestrator - Running with Administrator Privileges ")
print("========================================================")

import stat
import shutil

def _clear_readonly_and_remove(action, path, _):
    """Callback handler to strip Read-Only attributes and retry file/folder deletion."""
    try:
        os.chmod(path, stat.S_IWRITE)
        action(path)
    except PermissionError:
        print(f"[!] Warning: File/Directory is locked: {path}")
        print("    -> Make sure 'server.py' (TFTP/HTTP) is stopped and DISM is unmounted.")
    except Exception as err:
        print(f"[!] Failed to remove {path}: {err}")

def clean_sources_directory(target_path: Path):
    """Safely purges all contents inside the given directory without removing the folder itself."""
    if not target_path.is_dir():
        return

    print(f"[*] Purging staging folder: {target_path}")
    for item in target_path.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, onerror=_clear_readonly_and_remove)
            else:
                os.chmod(item, stat.S_IWRITE)
                item.unlink()
        except PermissionError:
            _clear_readonly_and_remove(item.unlink if item.is_file() else shutil.rmtree, item, None)
        except Exception as e:
            print(f"[!] Error deleting {item.name}: {e}")

def update_unattend_files(username, password):
    """Dynamically updates username and password in both unattend files."""
    config_dir = BASE_DIR / "customizable_configs"
    files = [
        config_dir / "autounattend.xml",
        config_dir / "unattend.xml"
    ]
    
    for file_path in files:
        if not file_path.exists():
            print(f"[-] Warning: Config file not found: {file_path}")
            continue
        
        try:
            # Register namespaces to preserve XML formatting structure
            ET.register_namespace('', "urn:schemas-microsoft-com:unattend")
            ET.register_namespace('wcm', "http://schemas.microsoft.com/WMIConfig/2002/State")
            ET.register_namespace('xsi', "http://www.w3.org/2001/XMLSchema-instance")
            
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Locate and update LocalAccount and AutoLogon fields safely across namespaces
            for elem in root.iter():
                if elem.tag.endswith('LocalAccount'):
                    for child in elem:
                        if child.tag.endswith('Name'):
                            child.text = username
                        elif child.tag.endswith('DisplayName'):
                            child.text = username
                        elif child.tag.endswith('Password'):
                            for sub in child:
                                if sub.tag.endswith('Value'):
                                    sub.text = password
                elif elem.tag.endswith('AutoLogon'):
                    for child in elem:
                        if child.tag.endswith('Username'):
                            child.text = username
                        elif child.tag.endswith('Password'):
                            for sub in child:
                                if sub.tag.endswith('Value'):
                                    sub.text = password
                                    
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            print(f"[+] Updated credentials successfully in: {file_path.relative_to(BASE_DIR)}")
        except Exception as e:
            print(f"[-] Error updating {file_path.name}: {e}")

# Helper to run PowerShell scripts
def run_ps(script_name):
    path = os.path.join(RootMDir, script_name)
    if not os.path.exists(path):
        path = os.path.join(RootMDir, "ps module", script_name)
    
    if os.path.exists(path):
        print(f"[*] Executing PowerShell script: {script_name}")
        subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", path], check=True)
    else:
        print(f"[-] Warning: Could not find script '{script_name}'")

# Helper to run Python scripts
def run_py(script_name):
    path = os.path.join(RootMDir, script_name)
    if not os.path.exists(path):
        path = os.path.join(RootMDir, "modules", script_name)
        
    if os.path.exists(path):
        print(f"[*] Executing Python script: {script_name}")
        script_dir = os.path.dirname(path)
        subprocess.run([sys.executable, path], cwd=script_dir, check=True)
    else:
        print(f"[-] Warning: Could not find script '{script_name}'")
        
if __name__ == "__main__":
    try:
        # Step 0: Configure Account Credentials for Unattend Files
        print("\n--- Windows Local Account Configuration ---")
        def_user = "admin"
        inp_user = input(f"Enter Account Username [Default: {def_user}]: ").strip()
        username = inp_user if inp_user else def_user

        password = input("Enter Account Password [Default: blank]: ").strip()

        print(f"[*] Applying credentials (Username: {username}) to configuration files...")
        update_unattend_files(username, password)
        print("-------------------------------------------\n")

        # Step 1: Run setup.ps1
        winpe_sources = BASE_DIR / "winpe" / "sources"
        clean_sources_directory(winpe_sources)
        run_ps("modules/setup.ps1")

        # Step 2: Run ISO Modifier
        if os.path.exists(os.path.join(RootMDir, "isomodifier.py")):
            run_py("isomodifier.py")
        elif os.path.exists(os.path.join(RootMDir, "modules", "iso_modifier.ps1")):
            run_ps("modules/iso_modifier.ps1")
        else:
            run_ps("modules/iso_modifier.ps1") 

        # Step 3: Run server and locks management
        run_py("modules/manage_locks.py")
        run_py("modules/server.py")

        print("\n[SUCCESS] All pipeline steps completed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"\n[-] Execution failed with exit code {e.returncode}")
        sys.exit(e.returncode)