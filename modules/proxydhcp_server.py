import socket
import threading
from config import SERVER_IP, CLIENT_LOCK

class ProxyDHCPServer:
    def __init__(self, host="0.0.0.0"):
        self.host = host

    def listen_port(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind((self.host, port))
            print(f"[ProxyDHCP] Listening on UDP port {port}...")
        except Exception as e:
            print(f"[ProxyDHCP] Warning on port {port}: {e}")
            return

        while True:
            try:
                data, addr = sock.recvfrom(2048)
                if len(data) < 240:
                    continue

                if data[236:240] == b"\x63\x82\x53\x63":
                    client_mac = data[28:34].hex(":")
                    if not CLIENT_LOCK.is_allowed_mac(client_mac):
                        continue

                    threading.Thread(
                        target=self.respond_proxy,
                        args=(sock, data, addr, port),
                        daemon=True
                    ).start()
            except Exception:
                pass

    def start(self):
        threading.Thread(target=self.listen_port, args=(67,), daemon=True).start()
        threading.Thread(target=self.listen_port, args=(4011,), daemon=True).start()

    def respond_proxy(self, sock, packet, addr, in_port):
        xid = packet[4:8]
        flags = packet[10:12]
        client_mac = packet[28:34]

        # Check if request comes from iPXE client
        is_ipxe = b"iPXE" in packet

        reply = bytearray(240)
        reply[0] = 2
        reply[1] = 1
        reply[2] = 6
        reply[4:8] = xid
        reply[10:12] = flags

        server_ip_bytes = socket.inet_aton(SERVER_IP)
        reply[20:24] = server_ip_bytes
        reply[28:34] = client_mac

        if is_ipxe:
            bootfile_bytes = f"http://{SERVER_IP}/boot.ipxe\x00".encode()
        else:
            bootfile_bytes = b"ipxe.efi\x00"

        reply[108 : 108 + len(bootfile_bytes)] = bootfile_bytes
        reply[236:240] = b"\x63\x82\x53\x63"

        options = b"".join([
            b"\x35\x01\x02",
            b"\x36\x04" + server_ip_bytes,
            b"\x3c\x09PXEClient",
            b"\x42\x04" + server_ip_bytes,
            b"\x43" + bytes([len(bootfile_bytes)]) + bootfile_bytes,
            b"\xff"
        ])

        reply.extend(options)
        target_addr = ("255.255.255.255", 68) if addr[0] == "0.0.0.0" else (addr[0], 4011 if in_port == 4011 else 68)

        try:
            sock.sendto(reply, target_addr)
            target_name = "boot.ipxe script" if is_ipxe else "ipxe.efi"
            print(f"[ProxyDHCP:{in_port}] Sent {target_name} offer -> {target_addr[0]}:{target_addr[1]} for MAC {client_mac.hex(':')}")
        except Exception as e:
            print(f"[ProxyDHCP] Send Error: {e}")

def start_proxydhcp_server():
    server = ProxyDHCPServer()
    server.start()