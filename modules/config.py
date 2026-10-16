import socket
from pathlib import Path
import json

ROOT_DIR = Path(__file__).parent.parent.resolve()
CONFIGS_DIR = ROOT_DIR / "configs"
WINPE_DIR = ROOT_DIR / "winpe"
MAC_FILE = CONFIGS_DIR / "allowed_macs.json"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

SERVER_IP = get_local_ip()

class MacLockManager:
    def __init__(self):
        self.allowed_macs = set()
        self.load_macs()

    def _clean_mac(self, mac_str: str) -> str:
        return mac_str.lower().replace(":", "").replace("-", "")

    def load_macs(self):
        if MAC_FILE.exists():
            try:
                with open(MAC_FILE, "r") as f:
                    data = json.load(f)
                    self.allowed_macs = {self._clean_mac(m) for m in data}
            except Exception:
                self.allowed_macs = set()
        else:
            default_mac = "00:0c:29:b7:9f:b8"
            self.allowed_macs = {self._clean_mac(default_mac)}
            self.save_macs()

    def save_macs(self):
        with open(MAC_FILE, "w") as f:
            json.dump(list(self.allowed_macs), f)

    def set_macs(self, mac_list: list[str]):
        cleaned = [self._clean_mac(m) for m in mac_list]
        self.allowed_macs = set(cleaned)
        self.save_macs()

    def is_allowed_mac(self, mac_str: str) -> bool:
        return self._clean_mac(mac_str) in self.allowed_macs
        
    def get_allowed_macs(self) -> list[str]:
        return list(self.allowed_macs)

CLIENT_LOCK = MacLockManager()