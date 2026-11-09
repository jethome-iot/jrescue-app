"""
Network management module using NetworkManager (nmcli).

The recovery image ships NetworkManager; it owns the radios and runs its own
DHCP client, so this module is a thin wrapper over `nmcli`. Devices are
discovered at runtime (no hard-coded wlan0/eth0), so the same code works on
boards with predictable interface names (e.g. mainline ethernet "end0") and on
boards without Wi-Fi at all.
"""

import os
import errno
import socket
import time
from concurrent.futures import ThreadPoolExecutor
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


def classify_wifi_error(text: str, reason: int = None, returncode: int = None) -> str:
    """Classify connection failures, using NM's numeric reason when available."""
    low = (text or '').lower()
    for needles, code in (
        (('networkmanager is not running', 'could not connect to networkmanager'), 'unavailable'),
        (('no network with ssid', 'ssid-not-found', 'no access point'), 'not_found'),
        (('ip configuration could not be reserved', 'ip-config', 'dhcp'), 'no_dhcp'),
        (('strictly unmanaged', 'not managed', 'wi-fi is disabled', 'wifi is disabled', 'rfkill'), 'radio_busy'),
    ):
        if any(needle in low for needle in needles):
            return code
    if '802-11-wireless-security.psk' in low and any(word in low for word in ('invalid', 'missing', 'length')):
        return 'bad_password_format'
    if returncode == 8:
        return 'unavailable'
    # NMDeviceStateReason values are stable and independent of nmcli's locale.
    code = {3: 'radio_busy', 5: 'no_dhcp', 6: 'no_dhcp', 7: 'wrong_password',
            8: 'auth_failed', 9: 'auth_failed', 10: 'auth_failed', 11: 'timeout',
            15: 'no_dhcp', 16: 'no_dhcp', 17: 'no_dhcp', 35: 'radio_busy',
            36: 'no_wifi', 53: 'not_found'}.get(reason)
    if code:
        return code
    if returncode == 3 or 'timed out' in low or 'timeout' in low:
        return 'timeout'
    if 'secrets were required' in low or 'no-secrets' in low:
        return 'wrong_password'
    if 'supplicant' in low or 'authentication failed' in low:
        return 'auth_failed'
    return 'unknown'


def check_interface_internet(device: dict) -> Optional[bool]:
    """Check public TCP reachability through this device, never another route.

    None means untested (no address/connection, or binding is unavailable).
    TCP success does not verify DNS, TLS certificates or a captive portal.
    """
    bind_option = getattr(socket, 'SO_BINDTODEVICE', None)
    if not device.get('connected') or not device.get('ip') or bind_option is None:
        return None
    for target in config.NETWORK_STATUS_TARGETS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                connection.settimeout(config.NETWORK_STATUS_TIMEOUT)
                connection.setsockopt(socket.SOL_SOCKET, bind_option,
                                      device['interface'].encode('utf-8')+b'\0')
                connection.bind((device['ip'], 0))
                connection.connect((target, 443))
                return True
        except OSError as exc:
            if exc.errno in (errno.EPERM, errno.EACCES, errno.ENODEV,
                              errno.EADDRNOTAVAIL, errno.ENOPROTOOPT):
                return None
        except (ValueError, TypeError):
            return None
    return False


class NetworkHandler:
    """Base class for network handlers"""

    def __init__(self, interface: str = None):
        self.wifi_interface = interface or config.WIFI_INTERFACE
        self.eth_interface = config.ETHERNET_INTERFACE
        self.last_error = ''
        self.last_error_code = ''

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

    def get_ethernet_status(self) -> List[dict]:
        """Return wired devices, including links that have no IP address."""
        raise NotImplementedError

    def get_network_status(self, check_internet=False) -> List[dict]:
        """Return every Ethernet/Wi-Fi device, including disconnected ones."""
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

    def _enumerate_devices(self) -> bool:
        """Discover Wi-Fi and Ethernet devices instead of assuming wlan0/eth0."""
        ret, out, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'],
            check=False, timeout=5
        )
        self._wifi_devices = []
        self._eth_devices = []
        if ret != 0:
            return False
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
        return True

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
        self.last_error, self.last_error_code = '', ''
        if not self.available:
            self.last_error_code = 'unavailable'
            return []
        if not self.has_wifi():
            self.last_error_code = 'no_wifi'
            return []

        print_info("Scanning for WiFi networks...")

        # Trigger a rescan (ignore "scanning already in progress"), then list.
        run_command(['nmcli', 'device', 'wifi', 'rescan'], check=False, timeout=15)
        time.sleep(2)

        returncode, stdout, stderr = run_command(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
            check=False, timeout=15
        )

        if returncode != 0:
            self.last_error = (stderr or stdout or '').strip()
            self.last_error_code = classify_wifi_error(self.last_error, returncode=returncode)
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
        self.last_error, self.last_error_code = '', ''
        if not self.available:
            self.last_error_code = 'unavailable'
            return False

        print_info(f"Connecting to '{ssid}'...")

        cmd = ['nmcli', '--wait', '35', 'device', 'wifi', 'connect', ssid]
        if password:
            cmd += ['password', password]
        if self.wifi_interface:
            cmd += ['ifname', self.wifi_interface]

        returncode, stdout, stderr = run_command(cmd, check=False, timeout=50)

        if returncode == 0:
            print_success(f"Connected to '{ssid}'")
            print_info(f"WiFi connected to {ssid}")
            wait_with_spinner(3, "Obtaining IP address")
            return True

        reason = None
        if self.wifi_interface:
            code, output, _ = run_command(
                ['nmcli', '-g', 'GENERAL.REASON', 'device', 'show', self.wifi_interface],
                check=False, timeout=5)
            if code == 0:
                try:
                    reason = int(output.strip().split()[0])
                except (ValueError, IndexError):
                    pass
        detail = (stderr or stdout or '').strip()
        self.last_error_code = classify_wifi_error(detail, reason, returncode)
        self.last_error = detail.replace(password, '***') if password else detail
        print_error(f"WiFi connection failed: {self.last_error}")
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

    def get_network_status(self, check_internet=False) -> List[dict]:
        """Read both device types without scanning, reconnecting or touching AP."""
        self.last_error = ''
        if not self.available or not self._enumerate_devices():
            self.last_error = 'NetworkManager status unavailable'
            return []
        devices = []
        for kind, names in (('ethernet', self._eth_devices), ('wifi', self._wifi_devices)):
            for name in names:
                ret, out, _ = run_command(
                    ['nmcli', '-t', '-f', 'GENERAL.STATE,IP4.ADDRESS', 'device', 'show', name],
                    check=False, timeout=5)
                fields = {}
                if ret == 0:
                    for line in out.splitlines():
                        parts = _nmcli_split(line)
                        if len(parts) >= 2:
                            fields[parts[0]] = parts[1]
                try:
                    state = int(fields.get('GENERAL.STATE', '').split()[0])
                except (ValueError, IndexError):
                    state = None
                carrier = None
                if kind == 'ethernet':
                    try:
                        with open(os.path.join('/sys/class/net', name, 'carrier')) as source:
                            carrier = source.read().strip() == '1'
                    except OSError:
                        pass
                devices.append({
                    'interface': name, 'kind': kind, 'state': state,
                    'connected': state == 100, 'carrier': carrier,
                    'ip': next((value.split('/')[0] for key, value in fields.items()
                                if key.startswith('IP4.ADDRESS') and value), None),
                    'internet': None,
                })
        if check_internet and devices:
            try:
                with ThreadPoolExecutor(max_workers=min(4, len(devices))) as pool:
                    results = list(pool.map(check_interface_internet, devices))
                for device, online in zip(devices, results):
                    device['internet'] = online
            except RuntimeError:
                # Resource exhaustion must not turn unknown into 'no internet'.
                pass
        return devices

    def get_ethernet_status(self) -> List[dict]:
        """Inspect auto-detected Ethernet interfaces without changing networking."""
        if not self.available:
            return []
        self._enumerate_devices()
        devices = []
        for device in self._eth_devices:
            ret, out, _ = run_command(
                ['nmcli', '-t', '-f', 'GENERAL.STATE,GENERAL.HWADDR,IP4.ADDRESS',
                 'device', 'show', device], check=False)
            if ret != 0:
                continue
            fields = {}
            for line in out.splitlines():
                parts = _nmcli_split(line)
                if len(parts) >= 2:
                    fields[parts[0]] = parts[1]
            link = None
            speed = None
            try:
                with open(os.path.join('/sys/class/net', device, 'carrier')) as source:
                    link = source.read().strip() == '1'
            except OSError:
                pass
            try:
                with open(os.path.join('/sys/class/net', device, 'speed')) as source:
                    value = int(source.read().strip())
                    speed = value if value > 0 else None
            except (OSError, ValueError):
                pass
            state = fields.get('GENERAL.STATE', '')
            devices.append({
                'interface': device,
                'connected': state.split(' ', 1)[0] == '100',
                'carrier': link,
                'ip': next((value.split('/')[0] for key, value in fields.items()
                            if key.startswith('IP4.ADDRESS') and value), None),
                'mac': fields.get('GENERAL.HWADDR') or None,
                'speed': speed,
            })
        return devices


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
