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


class NetworkManagerHandler(NetworkHandler):
    """Network management using NetworkManager (nmcli)"""

    def __init__(self, interface: str = None):
        super().__init__(interface)
        self.available = check_command_exists('nmcli')
        if self.available:
            print_info("NetworkManager (nmcli) detected")

    def scan_wifi(self) -> List[dict]:
        """Scan for WiFi networks using nmcli"""
        if not self.available:
            return []

        print_info("Scanning for WiFi networks...")

        # Rescan
        run_command(['nmcli', 'device', 'wifi', 'rescan'], check=False)
        time.sleep(2)

        # Get list
        returncode, stdout, stderr = run_command(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
            check=False
        )

        if returncode != 0:
            print_error(f"WiFi scan failed: {stderr}")
            return []

        networks = []
        seen_ssids = set()

        for line in stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split(':')
            if len(parts) >= 3:
                ssid = parts[0].strip()
                if ssid and ssid not in seen_ssids:
                    signal = parts[1].strip()
                    security = parts[2].strip() if parts[2].strip() else "Open"

                    networks.append({
                        'ssid': ssid,
                        'signal': signal,
                        'security': security
                    })
                    seen_ssids.add(ssid)

        return networks

    def connect_wifi(self, ssid: str, password: str = None) -> bool:
        """Connect to WiFi using nmcli"""
        if not self.available:
            return False

        print_info(f"Connecting to '{ssid}'...")

        # Build command
        if password:
            cmd = ['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password]
        else:
            cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]

        returncode, stdout, stderr = run_command(cmd, check=False)

        if returncode == 0:
            print_success(f"Connected to '{ssid}'")
            print_info(f"WiFi connected to {ssid}")

            # Wait for IP
            wait_with_spinner(3, "Obtaining IP address")
            return True
        else:
            print_error(f"Failed to connect: {stderr}")
            print_error(f"WiFi connection failed: {stderr}")
            return False

    def disconnect_wifi(self) -> bool:
        """Disconnect from WiFi using nmcli"""
        if not self.available:
            return False

        returncode, _, _ = run_command(
            ['nmcli', 'device', 'disconnect', self.wifi_interface],
            check=False
        )
        return returncode == 0

    def connect_ethernet(self) -> bool:
        """Connect to Ethernet using nmcli"""
        if not self.available:
            return False

        print_info("Configuring Ethernet connection...")

        # Bring up interface
        returncode, _, stderr = run_command(
            ['nmcli', 'device', 'connect', self.eth_interface],
            check=False
        )

        if returncode == 0:
            print_success("Ethernet connected")
            print_info("Ethernet connected")
            wait_with_spinner(3, "Obtaining IP address")
            return True
        else:
            print_error(f"Failed to connect: {stderr}")
            return False

    def get_connection_status(self) -> dict:
        """Get connection status using nmcli"""
        status = {
            'connected': False,
            'interface': None,
            'ssid': None,
            'ip': None
        }

        if not self.available:
            return status

        # Check WiFi
        returncode, stdout, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'device', 'status'],
            check=False
        )

        if returncode == 0:
            for line in stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 3:
                    device = parts[0]
                    state = parts[1]
                    connection = parts[2]

                    if state == 'connected':
                        status['connected'] = True
                        status['interface'] = device

                        # Get IP
                        ret, ip_out, _ = run_command(
                            ['nmcli', '-t', '-f', 'IP4.ADDRESS', 'device', 'show', device],
                            check=False
                        )
                        if ret == 0 and ip_out:
                            ip_line = ip_out.strip().split('\n')[0]
                            if ':' in ip_line:
                                status['ip'] = ip_line.split(':')[1].strip()
                                # Remove subnet mask if present
                                if '/' in status['ip']:
                                    status['ip'] = status['ip'].split('/')[0]

                        # Check if WiFi
                        if device == self.wifi_interface:
                            status['ssid'] = connection

                        break

        return status

    def get_all_interfaces(self) -> list:
        """Get all active network interfaces with their IP addresses"""
        interfaces = []

        if not self.available:
            return interfaces

        # Get all devices
        returncode, stdout, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'device', 'status'],
            check=False
        )

        if returncode == 0:
            for line in stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 3:
                    device = parts[0]
                    state = parts[1]
                    connection = parts[2]

                    if state == 'connected':
                        # Get IP
                        ret, ip_out, _ = run_command(
                            ['nmcli', '-t', '-f', 'IP4.ADDRESS', 'device', 'show', device],
                            check=False
                        )

                        ip = None
                        if ret == 0 and ip_out:
                            ip_line = ip_out.strip().split('\n')[0]
                            if ':' in ip_line:
                                ip = ip_line.split(':')[1].strip()
                                # Remove subnet mask if present (e.g. "10.181.102.134/24")
                                if '/' in ip:
                                    ip = ip.split('/')[0]

                        if ip:
                            interface_info = {
                                'interface': device,
                                'ip': ip,
                                'ssid': None,
                                'connected': True  # Has IP = connected
                            }

                            # Check if WiFi
                            if device == self.wifi_interface:
                                interface_info['ssid'] = connection

                            interfaces.append(interface_info)

        return interfaces


class WpaSupplicantHandler(NetworkHandler):
    """Network management using wpa_supplicant (wpa_cli)"""

    def __init__(self, interface: str = None):
        super().__init__(interface)
        self.available = check_command_exists('wpa_cli')
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
        """Ensure wpa_supplicant is running"""
        import os

        # Check if already running
        returncode, stdout, _ = run_command(['pgrep', 'wpa_supplicant'], check=False)
        if returncode == 0:
            return True

        # Try to start it
        print_info("Starting wpa_supplicant...")
        conf_file = f"/etc/wpa_supplicant/wpa_supplicant-{self.wifi_interface}.conf"

        # Create minimal config if doesn't exist
        if not os.path.exists(conf_file):
            os.makedirs(os.path.dirname(conf_file), exist_ok=True)
            with open(conf_file, 'w') as f:
                f.write("ctrl_interface=/var/run/wpa_supplicant\n")
                f.write("update_config=1\n")

        returncode, _, _ = run_command([
            'wpa_supplicant', '-B', '-i', self.wifi_interface,
            '-c', conf_file
        ], check=False)

        return returncode == 0

    def scan_wifi(self) -> List[dict]:
        """Scan for WiFi networks using wpa_cli"""
        if not self.available:
            return []

        if not self._ensure_wpa_supplicant_running():
            print_error("Could not start wpa_supplicant")
            return []

        print_info("Scanning for WiFi networks...")

        # wpa_cli scan is async; scan_results may be stale/empty if read too early.
        scan_timeout_s = float(getattr(config, 'WPA_SCAN_TIMEOUT', 6))
        scan_retries = int(getattr(config, 'WPA_SCAN_RETRIES', 2))
        poll_interval_s = float(getattr(config, 'WPA_SCAN_POLL_INTERVAL', 0.5))

        stdout = ""
        for attempt in range(scan_retries + 1):
            ret, scan_out, _ = self._wpa_cli('scan', check=False)

            # If wpa_supplicant is busy, wait a bit and retry triggering scan.
            if ret != 0 or ('FAIL-BUSY' in (scan_out or '')):
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

        if not stdout:
            return []

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

