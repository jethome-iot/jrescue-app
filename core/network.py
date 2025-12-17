"""
Network management module using wpa_supplicant (for busybox/minimal systems)
"""

import time
import subprocess
from typing import List, Optional, Tuple
import config
from utils import (
    run_command, check_command_exists, print_error, print_success,
    print_info, print_warning, wait_with_spinner
)


class NetworkHandler:
    """Base class for network handlers"""

    def __init__(self, interface: str = None):
        self.wifi_interface = interface or config.WIFI_INTERFACE
        self.eth_interface = config.ETHERNET_INTERFACE

    def scan_wifi(self) -> List[dict]:
        """Scan for WiFi networks. Returns list of dicts with SSID, signal, security"""
        raise NotImplementedError

    def connect_wifi(self, ssid: str, password: str = None) -> bool:
        """Connect to WiFi network"""
        raise NotImplementedError

    def disconnect_wifi(self) -> bool:
        """Disconnect from WiFi"""
        raise NotImplementedError

    def connect_ethernet(self) -> bool:
        """Connect to Ethernet (DHCP)"""
        raise NotImplementedError

    def get_connection_status(self) -> dict:
        """Get current connection status"""
        raise NotImplementedError

    def get_all_interfaces(self) -> list:
        """
        Get all active network interfaces with their IP addresses

        Returns:
            List of dicts with keys: interface, ip, ssid (for WiFi)
        """
        raise NotImplementedError

    def test_connectivity(self) -> bool:
        """Test connectivity to JetHome API for downloading images"""
        import socket

        print_info("Testing connectivity to JetHome API...")
        print()

        has_connectivity = False

        # 1. Get IP address and interface
        status = self.get_connection_status()
        if status['connected'] and status['ip']:
            print_success(f"✓ IP Address: {status['ip']} ({status['interface']})")
            if status['ssid']:
                print_info(f"  WiFi: {status['ssid']}")
        else:
            print_error("✗ No active network connection")
            return False

        # 2. Get default gateway
        returncode, stdout, _ = run_command(['ip', 'route', 'show', 'default'], check=False)
        if returncode == 0 and stdout:
            gateway = stdout.split()[2] if len(stdout.split()) > 2 else "unknown"
            print_success(f"✓ Gateway: {gateway}")
        else:
            print_warning("✗ No default gateway")

        print()

        # 3. Test connectivity to JetHome API
        print_info("Testing JetHome API (fw.jethome.com)...")

        # Try DNS resolution first
        api_host = "fw.jethome.com"
        api_ip = None
        try:
            api_ip = socket.gethostbyname(api_host)
            print_success(f"✓ DNS resolved: {api_host} → {api_ip}")
        except socket.gaierror:
            print_error(f"✗ Cannot resolve {api_host}")
            print_info("  Check DNS configuration or internet connection")
        except Exception as e:
            print_error(f"✗ DNS error: {e}")

        # Try to ping the API server
        if api_ip:
            returncode, _, _ = run_command(['ping', '-c', '2', '-W', '3', api_ip], check=False)
            if returncode == 0:
                print_success(f"✓ JetHome API is reachable")
                has_connectivity = True
            else:
                print_error(f"✗ Cannot reach JetHome API")
                print_info("  Network may have firewall blocking ICMP")

        print()

        if has_connectivity:
            print_success("✓ Ready to download images from JetHome API!")
        else:
            print_error("✗ Cannot reach JetHome API")
            print_info("Check your internet connection and try again")

        return has_connectivity


class WpaSupplicantHandler(NetworkHandler):
    """Network management using wpa_supplicant (wpa_cli)"""

    def __init__(self, interface: str = None):
        super().__init__(interface)
        self.available = check_command_exists('wpa_cli')
        # Cache last successful scan results to smooth out occasional empty scans
        self._last_scan_stdout: str = ""
        self._last_scan_ts: float = 0.0
        if self.available:
            print_info("wpa_supplicant (wpa_cli) detected")

    def _wpa_cli(self, *args: str, check: bool = False) -> Tuple[int, str, str]:
        """Run wpa_cli for current interface."""
        return run_command(['wpa_cli', '-i', self.wifi_interface, *args], check=check)

    def _wait_for_scan_results(self, timeout_s: float, poll_interval_s: float) -> str:
        """
        Poll wpa_cli scan_results until we get at least one network line (header + data),
        or until timeout. Returns raw stdout (possibly only header if no networks found).
        """
        start = time.monotonic()
        last_stdout = ""

        # Tiny initial delay helps avoid reading stale results immediately after scan trigger
        time.sleep(min(0.5, max(0.0, poll_interval_s)))

        while (time.monotonic() - start) < timeout_s:
            returncode, stdout, _ = self._wpa_cli('scan_results', check=False)
            if returncode == 0 and stdout:
                last_stdout = stdout
                lines = stdout.strip().split('\n')
                # Header line + at least one BSS line
                if len(lines) > 1:
                    return stdout

            time.sleep(max(0.1, poll_interval_s))

        return last_stdout

    def _ensure_wpa_supplicant_running(self) -> bool:
        """
        Ensure wpa_supplicant is running and controllable via wpa_cli.

        Notes for minimal/busybox systems:
        - Don't rely on `pgrep` (often disabled in BusyBox).
        - Prefer a functional check via `wpa_cli ping` (control socket ready).
        - If we do need to start wpa_supplicant, use the same args as init script.
        """
        import os

        # 1) Fast-path: control socket responds
        ret, out, _ = self._wpa_cli('ping', check=False)
        if ret == 0 and 'PONG' in (out or ''):
            return True

        # 2) BusyBox-friendly process check: if it's running, it might just not be ready yet
        ret, out, _ = run_command(['pidof', 'wpa_supplicant'], check=False)
        if ret == 0 and (out or '').strip():
            time.sleep(0.5)
            ret2, out2, _ = self._wpa_cli('ping', check=False)
            return ret2 == 0 and 'PONG' in (out2 or '')

        # 3) Start it (match board init script)
        print_info("Starting wpa_supplicant...")
        os.makedirs('/run/wpa_supplicant', exist_ok=True)

        returncode, _, _ = run_command([
            'wpa_supplicant', '-B',
            '-i', self.wifi_interface,
            '-c', '/etc/wpa_supplicant.conf',
            '-C', '/run/wpa_supplicant',
        ], check=False)

        if returncode != 0:
            return False

        # Give it a moment to create the control socket
        time.sleep(0.5)
        ret3, out3, _ = self._wpa_cli('ping', check=False)
        return ret3 == 0 and 'PONG' in (out3 or '')

    def scan_wifi(self) -> List[dict]:
        """Scan for WiFi networks using wpa_cli"""
        if not self.available:
            return []

        if not self._ensure_wpa_supplicant_running():
            print_error("Could not start wpa_supplicant")
            return []

        print_info("Scanning for WiFi networks...")

        # wpa_cli scan is async; scan_results may be stale/empty if read too early.
        scan_timeout_s = float(getattr(config, 'WPA_SCAN_TIMEOUT', 12))
        scan_retries = int(getattr(config, 'WPA_SCAN_RETRIES', 3))
        poll_interval_s = float(getattr(config, 'WPA_SCAN_POLL_INTERVAL', 0.5))
        cache_ttl_s = float(getattr(config, 'WPA_SCAN_CACHE_TTL', 300))

        stdout = ""
        for attempt in range(scan_retries + 1):
            ret, scan_out, _ = self._wpa_cli('scan', check=False)

            # If wpa_supplicant is busy, a scan is already running.
            # Don't just re-trigger: wait for current scan to finish and fetch results.
            if 'FAIL-BUSY' in (scan_out or ''):
                stdout = self._wait_for_scan_results(
                    timeout_s=min(scan_timeout_s, 6.0),
                    poll_interval_s=poll_interval_s
                ) or ""
                if len(stdout.strip().splitlines()) > 1:
                    break
                time.sleep(1)
                continue

            # Any other error: small delay and retry
            if ret != 0:
                time.sleep(1)
                continue

            stdout = self._wait_for_scan_results(timeout_s=scan_timeout_s, poll_interval_s=poll_interval_s) or ""
            if stdout.strip():
                lines = stdout.strip().split('\n')
                if len(lines) > 1:  # got at least one network
                    break

            # No networks yet (or only header). Small delay then retry scan.
            if attempt < scan_retries:
                time.sleep(1)

        # If scan didn't yield anything useful, fall back to last known results
        # (helps with flaky timing where scan_results occasionally returns only header).
        if (not stdout) or (len(stdout.strip().splitlines()) <= 1):
            now = time.monotonic()
            if self._last_scan_stdout and (now - self._last_scan_ts) < cache_ttl_s:
                stdout = self._last_scan_stdout
            else:
                return []
        else:
            # Cache last successful scan output (raw)
            self._last_scan_stdout = stdout
            self._last_scan_ts = time.monotonic()

        networks = []
        seen_ssids = set()

        lines = stdout.strip().split('\n')
        for line in lines[1:]:  # Skip header
            parts = line.split('\t')
            if len(parts) >= 5:
                ssid = parts[4].strip()
                if ssid and ssid not in seen_ssids:
                    # Signal strength in dBm, convert to percentage (rough approximation)
                    try:
                        signal_dbm = int(parts[2])
                        signal = max(0, min(100, 2 * (signal_dbm + 100)))
                    except (ValueError, IndexError):
                        signal = 0

                    # Security
                    flags = parts[3] if len(parts) > 3 else ""
                    if 'WPA' in flags or 'WEP' in flags:
                        security = "Secured"
                    else:
                        security = "Open"

                    networks.append({
                        'ssid': ssid,
                        'signal': str(signal),
                        'security': security
                    })
                    seen_ssids.add(ssid)

        return networks

    def connect_wifi(self, ssid: str, password: str = None) -> bool:
        """Connect to WiFi using wpa_cli"""
        if not self.available:
            return False

        if not self._ensure_wpa_supplicant_running():
            return False

        print_info(f"Connecting to '{ssid}'...")

        # Add network
        returncode, stdout, _ = run_command(
            ['wpa_cli', '-i', self.wifi_interface, 'add_network'],
            check=False
        )

        if returncode != 0:
            print_error("Failed to add network")
            return False

        network_id = stdout.strip().split('\n')[-1].strip()

        # Set SSID
        run_command([
            'wpa_cli', '-i', self.wifi_interface,
            'set_network', network_id, 'ssid', f'"{ssid}"'
        ], check=False)

        # Set password or configure open network
        if password:
            run_command([
                'wpa_cli', '-i', self.wifi_interface,
                'set_network', network_id, 'psk', f'"{password}"'
            ], check=False)
        else:
            run_command([
                'wpa_cli', '-i', self.wifi_interface,
                'set_network', network_id, 'key_mgmt', 'NONE'
            ], check=False)

        # Enable network
        returncode, _, _ = run_command([
            'wpa_cli', '-i', self.wifi_interface,
            'enable_network', network_id
        ], check=False)

        if returncode != 0:
            print_error("Failed to enable network")
            return False

        # Select network
        run_command([
            'wpa_cli', '-i', self.wifi_interface,
            'select_network', network_id
        ], check=False)

        # Save configuration
        run_command(['wpa_cli', '-i', self.wifi_interface, 'save_config'], check=False)

        # Wait for connection
        wait_with_spinner(5, "Connecting to WiFi")

        # Get IP with dhclient or dhcpcd
        print_info("Obtaining IP address...")
        if check_command_exists('dhclient'):
            run_command(['dhclient', self.wifi_interface], check=False)
        elif check_command_exists('dhcpcd'):
            run_command(['dhcpcd', self.wifi_interface], check=False)
        elif check_command_exists('udhcpc'):
            run_command(['udhcpc', '-i', self.wifi_interface], check=False)

        time.sleep(2)

        # Check if we got IP
        returncode, stdout, _ = run_command(['ip', 'addr', 'show', self.wifi_interface], check=False)
        if 'inet ' in stdout:
            print_success(f"Connected to '{ssid}'")
            print_info(f"WiFi connected to {ssid}")
            return True
        else:
            print_error("Connected but failed to obtain IP address")
            return False

    def disconnect_wifi(self) -> bool:
        """Disconnect from WiFi"""
        if not self.available:
            return False

        run_command(['wpa_cli', '-i', self.wifi_interface, 'disconnect'], check=False)
        return True

    def connect_ethernet(self) -> bool:
        """Connect to Ethernet"""
        print_info("Configuring Ethernet connection...")

        # Bring up interface
        returncode, _, _ = run_command(['ip', 'link', 'set', self.eth_interface, 'up'], check=False)

        if returncode != 0:
            print_error("Failed to bring up Ethernet interface")
            return False

        time.sleep(1)

        # Get IP with DHCP
        if check_command_exists('dhclient'):
            returncode, _, _ = run_command(['dhclient', self.eth_interface], check=False)
        elif check_command_exists('dhcpcd'):
            returncode, _, _ = run_command(['dhcpcd', self.eth_interface], check=False)
        elif check_command_exists('udhcpc'):
            returncode, _, _ = run_command(['udhcpc', '-i', self.eth_interface], check=False)
        else:
            print_error("No DHCP client found")
            return False

        wait_with_spinner(3, "Obtaining IP address")

        # Check if we got IP
        returncode, stdout, _ = run_command(['ip', 'addr', 'show', self.eth_interface], check=False)
        if 'inet ' in stdout:
            print_success("Ethernet connected")
            print_info("Ethernet connected")
            return True
        else:
            print_error("Failed to obtain IP address")
            return False

    def get_connection_status(self) -> dict:
        """Get connection status"""
        import re

        status = {
            'connected': False,
            'interface': None,
            'ssid': None,
            'ip': None
        }

        # Check WiFi
        if self.available:
            returncode, stdout, _ = run_command(
                ['wpa_cli', '-i', self.wifi_interface, 'status'],
                check=False
            )

            if returncode == 0 and 'wpa_state=COMPLETED' in stdout:
                status['connected'] = True
                status['interface'] = self.wifi_interface

                # Extract SSID
                for line in stdout.split('\n'):
                    if line.startswith('ssid='):
                        status['ssid'] = line.split('=', 1)[1].strip()
                        break

        # Check for IP on WiFi interface
        returncode, stdout, _ = run_command(['ip', 'addr', 'show', self.wifi_interface], check=False)
        if returncode == 0:
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
            if match:
                status['ip'] = match.group(1)
                status['connected'] = True
                status['interface'] = self.wifi_interface

        # Check Ethernet if WiFi not connected
        if not status['connected']:
            returncode, stdout, _ = run_command(['ip', 'addr', 'show', self.eth_interface], check=False)
            if returncode == 0:
                match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
                if match:
                    status['ip'] = match.group(1)
                    status['connected'] = True
                    status['interface'] = self.eth_interface

        return status

    def get_all_interfaces(self) -> list:
        """Get all active network interfaces with their IP addresses"""
        import re

        interfaces = []

        # Check WiFi interface
        returncode, stdout, _ = run_command(['ip', 'addr', 'show', self.wifi_interface], check=False)
        if returncode == 0:
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
            if match:
                wifi_ip = match.group(1)

                # Get SSID if connected
                ssid = None
                if self.available:
                    ret, wpa_out, _ = run_command(
                        ['wpa_cli', '-i', self.wifi_interface, 'status'],
                        check=False
                    )
                    if ret == 0 and 'wpa_state=COMPLETED' in wpa_out:
                        for line in wpa_out.split('\n'):
                            if line.startswith('ssid='):
                                ssid = line.split('=', 1)[1].strip()
                                break

                interfaces.append({
                    'interface': self.wifi_interface,
                    'ip': wifi_ip,
                    'ssid': ssid,
                    'connected': True  # Has IP = connected
                })

        # Check Ethernet interface
        returncode, stdout, _ = run_command(['ip', 'addr', 'show', self.eth_interface], check=False)
        if returncode == 0:
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', stdout)
            if match:
                interfaces.append({
                    'interface': self.eth_interface,
                    'ip': match.group(1),
                    'ssid': None,
                    'connected': True  # Has IP = connected
                })

        return interfaces


def get_network_handler() -> Optional[NetworkHandler]:
    """
    Return wpa_supplicant network handler (for busybox/minimal systems)
    """
    # Use wpa_supplicant only (no NetworkManager dependency)
    wpa_handler = WpaSupplicantHandler()
    if wpa_handler.available:
        print_success("Using wpa_supplicant (wpa_cli)")
        return wpa_handler

    print_error("wpa_supplicant not found!")
    print_warning("Please install wpa_supplicant: apt install wpa_supplicant")
    return None

