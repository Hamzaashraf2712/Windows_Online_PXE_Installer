# ⚠️ EXTREME DATA DESTRUCTION WARNING — READ BEFORE PROCEEDING ⚠️

> **ATTENTION:** This software interacts directly with raw disk partitions, low-level disk formatting ('Diskpart'), automated wiping utilities, and network deployment protocols. 
> **RUN AT YOUR OWN RISK:** The authors and contributors accept **ABSOLUTELY NO RESPONSIBILITY OR LIABILITY** for any data loss, system failure, corruption, or hardware damage whatsoever. 
> **USING THIS WITHOUT PROPER INSTRUCTIONS CAN DESTROY ALL YOUR DATA:** Executing these scripts on an unintended machine, hard drive, or volume will permanently wipe all stored files, operating systems, and partitions beyond recovery. 
> **VERIFY YOUR TARGETS:** Always double-check disk numbers, target environments, and configuration states before initiating any automated wiping or deployment commands.

---

# PXE Orchestrator & Automated Windows Deployment System

A robust, zero-touch, network-based Windows deployment and PXE staging system built using **Python**, **PowerShell**, and native **Windows deployment utilities (DISM, Diskpart, BCDBoot)**. Designed for speed, automation, and full control over local account staging and dynamic partition management.

## Credits

* **iPXE EFI binary (`ipxe.efi`):** Provided by the [FOG Project](https://github.com/FOGProject/fogproject/blob/master/packages/tftp/ipxe.efi) and built from the [iPXE project](https://github.com/ipxe/ipxe).
* **wimboot:** Provided by the [iPXE project](https://github.com/ipxe/wimboot), which publishes the binary used by this setup.

See the upstream projects for their licensing terms and notices.

---

## ⚙️ Core Architecture & Component Scripts

* **`setup.bat`:** Main entry point script to initialize setup, trigger cleanup, and fetch dependencies.
* **`main.py` (Master Orchestrator):** Handles self-elevation to administrator privileges, prompts for secure local administrator credentials, dynamically injects user configs into unattended XML files, and orchestrates the pipeline execution flow.
* **`clean.ps1` (Isolated Staging Purge):** Automatically cleans, purges, and re-initializes the project workspace directories (`winpe`, `scripts`, etc.) to prevent stale files from interfering with new deployments.
* **`modules/setup.ps1`:** Prerequisite manager that calls `clean.ps1` and fetches required net-boot binaries (`ipxe.efi` and `wimboot`) from upstream sources.
* **`modules/server.py` (HTTP / PXE Server Core):** Manages client inventory via MAC address tracking (which can be obtained directly from your machine's BIOS or network boot screen), dynamically compiles customized batch and Diskpart scripts per client, and streams deployment packages over TCP port 80.

---

## 🚀 Streamlined Deployment Strategies

When a client boots into PXE and connects to the server, you are presented with three deployment choices:

1. **[1] Clean Wipe Target Disk:** Full GPT disk sanitization, EFI system partition layout creation, MSR creation, and primary NTFS Windows formatting.
2. **[2] Split Target Disk:** Custom OS partition sizing (in GB) with an optional secondary Data partition created out of remaining disk space.
3. **[3] Format OS Partition & Install Automatically:** Automatically scans and detects the existing Windows OS partition (`ntoskrnl.exe`), formats only that specific drive, and installs the fresh image while leaving all other user data drives and partitions completely untouched.

---

## 🔍 Finding Your Client MAC Address

Before or during deployment, you can locate your target client's MAC address easily:

* **In BIOS / UEFI Firmware:** Look under the network configuration, device information, or adapter settings screen.
* **On Network Boot / iPXE Screen:** The MAC address is displayed directly on the screen when the client initiates the PXE network boot sequence.

---

## ⚠️ ADDITIONAL WARNING: DATA LOSS LIABILITY & REPEATED NOTICE

By downloading, cloning, modifying, or executing any part of this repository, you acknowledge and agree that:

1. You are running this software **entirely at your own risk**.
2. The developers are **not responsible** for any type of data loss, business interruption, or file destruction.
3. Improper configuration, incorrect disk indexing, or lack of proper understanding of these scripts **can destroy all your data instantly**. Ensure you test exclusively in isolated, non-production laboratory environments.

---

## 🚀 Getting Started & Execution

1. **Verify Backups:** Ensure all critical data on target test machines is fully backed up.
2. **Download/Clone:** Download/clone this repository and have your standard Windows ISO ready.
3. **Run Setup:** Execute **`setup.bat`** as Administrator to automatically clean workspaces, verify directories, and fetch network boot binaries.
4. **PXE Boot Client:** Boot your target machine over the network (noting its MAC address from the BIOS or boot screen) and select your deployment strategy on the host server console.
