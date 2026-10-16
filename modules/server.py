import threading
import time
from config import ROOT_DIR, SERVER_IP, CLIENT_LOCK
from proxydhcp_server import start_proxydhcp_server
from tftp_server import start_tftp_server
from http_server import start_http_server

IPXE_TEMPLATE = """#!ipxe
kernel http://{server_ip}/wimboot
initrd http://{server_ip}/winpe/sources/boot.wim boot.wim
boot
"""

def main():
    ipxe_dir = ROOT_DIR / "ipxe_files"
    for filename in ("boot.ipxe", "default.ipxe", "autoexec.ipxe"):
        (ipxe_dir / filename).write_text(IPXE_TEMPLATE.format(server_ip=SERVER_IP), encoding="utf-8")

    print("=" * 60)
    print(f" Pure Python PXE Appliance running on {SERVER_IP}")
    print(f" Locked strictly to allowed MACs: {CLIENT_LOCK.get_allowed_macs()}")
    print("=" * 60)

    tftp_thread = threading.Thread(target=start_tftp_server, daemon=True)
    proxy_thread = threading.Thread(target=start_proxydhcp_server, daemon=True)
    http_thread = threading.Thread(target=start_http_server, daemon=True)

    tftp_thread.start()
    proxy_thread.start()
    http_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Shutting down PXE Appliance...")

if __name__ == "__main__":
    main()
