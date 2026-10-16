import socket
import struct
import threading
from pathlib import Path
from config import ROOT_DIR, WINPE_DIR

class TFTPServer:
    def __init__(self, host="0.0.0.0", port=69):
        self.host = host
        self.port = port

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        print(f"[TFTP] Listening on UDP port {self.port}...")

        while True:
            try:
                data, addr = sock.recvfrom(1024)
                if len(data) < 2:
                    continue

                opcode = struct.unpack("!H", data[:2])[0]
                if opcode == 1:
                    threading.Thread(target=self.handle_rrq, args=(addr, data), daemon=True).start()
            except Exception:
                pass

    def resolve_file(self, raw_filename):
        clean_path = raw_filename.replace("\\", "/").strip("/")
        requested_name = Path(clean_path).name.lower()

        direct_pe = WINPE_DIR / clean_path
        if direct_pe.exists() and direct_pe.is_file():
            return direct_pe

        direct_root = ROOT_DIR / clean_path
        if direct_root.exists() and direct_root.is_file():
            return direct_root

        for p in WINPE_DIR.rglob("*"):
            if p.is_file() and p.name.lower() == requested_name:
                return p

        for p in ROOT_DIR.rglob("*"):
            if p.is_file() and p.name.lower() == requested_name:
                return p

        return None

    def handle_rrq(self, addr, data):
        parts = data[2:].split(b"\x00")
        if len(parts) < 2:
            return

        raw_filename = parts[0].decode("utf-8", errors="ignore")
        
        options = {}
        i = 2
        while i + 1 < len(parts):
            opt_key = parts[i].decode("utf-8", errors="ignore").lower()
            opt_val = parts[i+1].decode("utf-8", errors="ignore")
            if opt_key:
                options[opt_key] = opt_val
            i += 2

        file_path = self.resolve_file(raw_filename)

        if not file_path:
            print(f"[TFTP] 404 File Not Found: '{raw_filename}' requested by {addr[0]}")
            return

        file_size = file_path.stat().st_size
        print(f"[TFTP] Serving '{file_path.name}' ({file_size} bytes) for request '{raw_filename}' to {addr[0]}:{addr[1]}")

        tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        blksize = 1456

        if "blksize" in options:
            try:
                blksize = int(options["blksize"])
            except ValueError:
                blksize = 1456

        if "blksize" in options or "tsize" in options:
            oack_pkt = bytearray(b"\x00\x06")
            if "blksize" in options:
                oack_pkt.extend(b"blksize\x00" + str(blksize).encode() + b"\x00")
            if "tsize" in options:
                oack_pkt.extend(b"tsize\x00" + str(file_size).encode() + b"\x00")

            for _ in range(3):
                tx_sock.sendto(oack_pkt, addr)
                tx_sock.settimeout(2.0)
                try:
                    ack, _ = tx_sock.recvfrom(1024)
                    ack_opcode, ack_block = struct.unpack("!HH", ack[:4])
                    if ack_opcode == 4 and ack_block == 0:
                        break
                except socket.timeout:
                    continue

        block_num = 1
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(blksize)
                pkt = struct.pack("!HH", 3, block_num) + chunk

                for _ in range(3):
                    tx_sock.sendto(pkt, addr)
                    tx_sock.settimeout(2.0)
                    try:
                        ack, _ = tx_sock.recvfrom(1024)
                        ack_opcode, ack_block = struct.unpack("!HH", ack[:4])
                        if ack_opcode == 4 and ack_block == block_num:
                            break
                    except socket.timeout:
                        continue

                if len(chunk) < blksize:
                    break
                block_num = (block_num + 1) % 65536

        tx_sock.close()

def start_tftp_server():
    server = TFTPServer()
    server.start()
