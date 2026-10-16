import subprocess
import re
import ipaddress
import concurrent.futures
from config import SERVER_IP, CLIENT_LOCK

def ping_subnet():
    """Performs a quick parallel ping sweep across the local subnet to populate ARP table."""
    try:
        # Extracts base subnet from SERVER_IP (e.g., 192.168.0.x)
        subnet_prefix = ".".join(SERVER_IP.split(".")[:3])
        network = ipaddress.ip_network(f"{subnet_prefix}.0/24", strict=False)
        print(f"[*] Scanning subnet {network} to discover active devices...")
        
        def ping_host(ip):
            ip_str = str(ip)
            subprocess.run(f"ping -n 1 -w 50 {ip_str}", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
            executor.map(ping_host, network.hosts())
        print("[+] Scan complete.")
    except Exception as e:
        print(f"[!] Subnet scan warning: {e}")

def get_arp_devices():
    """Reads local ARP cache and extracts active IP and MAC pairs, filtering out clutter."""
    devices = []
    server_prefix = ".".join(SERVER_IP.split(".")[:3])
    
    try:
        output = subprocess.check_output("arp -a", shell=True).decode()
        pattern = re.compile(r'((?:[0-9]{1,3}\.){3}[0-9]{1,3})\s+(([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})')
        
        for match in pattern.findall(output):
            ip = match[0]
            mac = match[1]
            clean_mac = mac.replace(":", "").replace("-", "").lower()
            
            # Filter out broadcast, multicast, loopback, and foreign virtual subnets
            if ip == SERVER_IP:
                continue
            if not ip.startswith(server_prefix):
                continue
            if clean_mac == "ffffffffffff" or clean_mac.startswith("01005e"):
                continue
                
            devices.append({"ip": ip, "mac": mac})
    except Exception as e:
        print(f"[ERROR] Reading ARP table failed: {e}")
    return devices

def validate_and_lock_macs(raw_mac_list):
    cleaned_macs = []
    for m in raw_mac_list:
        m_clean = m.strip()
        if len(m_clean.replace(":", "").replace("-", "")) != 12:
            print(f"[WARNING] Invalid MAC format detected: '{m_clean}'")
            continue
        cleaned_macs.append(m_clean)

    if len(cleaned_macs) != len(set(cleaned_macs)):
        print("[!] Duplicate MAC addresses found. Removing duplicates.")
        cleaned_macs = list(set(cleaned_macs))

    if len(cleaned_macs) > 1:
        print("\n--------------------------------------------------")
        print(f"[ATTENTION] Locking in {len(cleaned_macs)} devices simultaneously.")
        print("--------------------------------------------------\n")

    CLIENT_LOCK.set_macs(cleaned_macs)
    print(f"[SUCCESS] Successfully locked in {len(cleaned_macs)} device(s):")
    for mac in CLIENT_LOCK.get_allowed_macs():
        print(f" -> {mac}")

def main():
    print("==========================================")
    print("       PXE MAC ADDRESS LOCK MANAGER       ")
    print("==========================================")
    
    ping_subnet()
    devices = get_arp_devices()
    
    print("\n--- Discovered Network Devices ---")
    if not devices:
        print("No active devices found on the primary subnet.")
    else:
        for idx, dev in enumerate(devices, 1):
            is_locked = CLIENT_LOCK.is_allowed_mac(dev['mac'])
            status = "[LOCKED IN]" if is_locked else ""
            print(f" [{idx}] IP: {dev['ip']} | MAC: {dev['mac']} {status}")

    print("\n--- Current Locked MACs ---")
    print(CLIENT_LOCK.get_allowed_macs())

    print("\nOptions:")
    print(" 1. Enter device number(s) from the list above (comma-separated, e.g., 1,3)")
    print(" 2. Type raw MAC address(es) manually")
    
    choice = input("\nEnter selection or MACs to lock: ").strip()
    if not choice:
        print("[!] Aborted.")
        return

    selected_macs = []
    parts = [p.strip() for p in choice.split(",")]
    for part in parts:
        if part.isdigit() and devices:
            idx = int(part) - 1
            if 0 <= idx < len(devices):
                selected_macs.append(devices[idx]['mac'])
            else:
                print(f"[!] Index {part} is out of range.")
        else:
            selected_macs.append(part)

    if selected_macs:
        validate_and_lock_macs(selected_macs)
    else:
        print("[!] No valid devices selected.")

if __name__ == "__main__":
    main()