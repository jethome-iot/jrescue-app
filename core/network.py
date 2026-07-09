"""
Network management module using NetworkManager (nmcli).

The recovery image ships NetworkManager; it owns the radios and runs its own
DHCP client, so this module is a thin wrapper over `nmcli`. Devices are
discovered at runtime (no hard-coded wlan0/eth0), so the same code works on
boards with predictable interface names (e.g. mainline ethernet "end0") and on
boards without Wi-Fi at all.
"""

import time
from typing import List, Optional
import config
from utils import (
    run_command, check_command_exists, print_error, print_success,
    print_info, print_warning, wait_with_spinner
)


def _nmcli_split(line: str) -> List[str]:
    """Split one line of `nmcli -t` (terse) output on unescaped ':'.

    nmcli escapes literal ':' and '\\' in field values with a backslash, so a
    naive str.split(':') mangles SSIDs/connection names that contain a colon.
    """
    fields = []
    cur = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == '\\' and i + 1 < n:
            cur.append(line[i + 1])
            i += 2
            continue
        if c == ':':
            fields.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    fields.append(''.join(cur))
    return fields


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

    def has_wifi(self) -> bool:
        """Whether the board has a Wi-Fi device (frontends hide Wi-Fi UI if not)"""
        return True

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
        self._wifi_devices: List[str] = []
        self._eth_devices: List[str] = []
        if self.available:
            self._enumerate_devices()

    def _enumerate_devices(self) -> None:
        """Discover Wi-Fi and Ethernet devices instead of assuming wlan0/eth0."""
        ret, out, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'],
            check=False
        )
        if ret != 0 or not out:
            return

        for line in out.strip().split('\n'):
            if not line:
                continue
            fields = _nmcli_split(line)
            if len(fields) < 2:
                continue
            device, dtype = fields[0], fields[1]
            if dtype == 'wifi':
                self._wifi_devices.append(device)
            elif dtype == 'ethernet':
                self._eth_devices.append(device)

        if self._wifi_devices:
            self.wifi_interface = self._wifi_devices[0]
        if self._eth_devices:
            self.eth_interface = self._eth_devices[0]

    def has_wifi(self) -> bool:
        return bool(self._wifi_devices)

    def _ip_of_device(self, device: str) -> Optional[str]:
        """Return the first IPv4 address of a device (without the /prefix)."""
        ret, out, _ = run_command(
            ['nmcli', '-t', '-f', 'IP4.ADDRESS', 'device', 'show', device],
            check=False
        )
        if ret != 0 or not out:
            return None
        first = out.strip().split('\n')[0]
        fields = _nmcli_split(first)
        if len(fields) < 2 or not fields[1]:
            return None
        return fields[1].split('/')[0]

    def scan_wifi(self) -> List[dict]:
        """Scan for WiFi networks using nmcli"""
        if not self.available or not self.has_wifi():
            return []

        print_info("Scanning for WiFi networks...")

        # Trigger a rescan (ignore "scanning already in progress"), then list.
        run_command(['nmcli', 'device', 'wifi', 'rescan'], check=False)
        time.sleep(2)

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
            fields = _nmcli_split(line)
            if len(fields) < 3:
                continue
            ssid = fields[0].strip()
            if not ssid or ssid in seen_ssids:
                continue
            signal = fields[1].strip()
            security = fields[2].strip() if fields[2].strip() else "Open"
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

        cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
        if password:
            cmd += ['password', password]
        if self.wifi_interface:
            cmd += ['ifname', self.wifi_interface]

        returncode, stdout, stderr = run_command(cmd, check=False)

        if returncode == 0:
            print_success(f"Connected to '{ssid}'")
            print_info(f"WiFi connected to {ssid}")
            wait_with_spinner(3, "Obtaining IP address")
            return True

        print_error(f"Failed to connect: {stderr}")
        print_error(f"WiFi connection failed: {stderr}")
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

        returncode, stdout, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'device', 'status'],
            check=False
        )
        if returncode != 0:
            return status

        for line in stdout.strip().split('\n'):
            fields = _nmcli_split(line)
            if len(fields) < 3:
                continue
            device, state, connection = fields[0], fields[1], fields[2]
            if state != 'connected':
                continue

            status['connected'] = True
            status['interface'] = device
            status['ip'] = self._ip_of_device(device)
            if device in self._wifi_devices:
                status['ssid'] = connection
            break

        return status

    def get_all_interfaces(self) -> list:
        """Get all active network interfaces with their IP addresses"""
        interfaces = []

        if not self.available:
            return interfaces

        returncode, stdout, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'device', 'status'],
            check=False
        )
        if returncode != 0:
            return interfaces

        for line in stdout.strip().split('\n'):
            fields = _nmcli_split(line)
            if len(fields) < 3:
                continue
            device, state, connection = fields[0], fields[1], fields[2]
            if state != 'connected':
                continue

            ip = self._ip_of_device(device)
            if not ip:
                continue

            interfaces.append({
                'interface': device,
                'ip': ip,
                'ssid': connection if device in self._wifi_devices else None,
                'connected': True  # Has IP = connected
            })

        return interfaces


def get_network_handler() -> Optional[NetworkHandler]:
    """
    Return the NetworkManager (nmcli) network handler.

    The recovery image ships NetworkManager; if nmcli is missing the build is
    broken, so we fail loudly rather than falling back to a legacy stack.
    """
    handler = NetworkManagerHandler()
    if handler.available:
        return handler

    print_error("NetworkManager (nmcli) not found!")
    print_warning("The recovery image must ship NetworkManager")
    return None
