"""
Wi-Fi setup-AP provisioning — the "connect me to your home Wi-Fi" flow.

On a board with no wired network the recovery raises its own Wi-Fi Access Point
(hostapd + dnsmasq, driven by the system unit jrescue-ap.service). A phone joins
that AP and, through the web portal, picks the home Wi-Fi and enters its
password. This module owns the AP<->STA *policy*: it stops the AP, joins the
chosen network, verifies real connectivity (an IP *and* a reachable gateway)
and — only on failure — rolls back to the AP so the user can retry.

The radio is single (see AGENTS.md / the driver notes): it is either an AP or an
STA, never both. Provisioning is therefore strictly sequential, and the phone
WILL be disconnected the instant the AP is stopped — the portal warns about it.

System vs app split: the shell side (usr/bin/jrescue-ap-up / jrescue-ap-down,
started via systemctl) owns the radio primitives — hostapd, dnsmasq, the gateway
IP, handing the device back to NetworkManager. This module never execs
hostapd/dnsmasq; it only start/stops the service and drives the nmcli-connect
handoff. The two halves talk through systemctl and the runtime files in
/run/jrescue/ (ap-creds.txt, wifi-scan.txt).
"""

import threading
import time
from typing import Callable, Dict, List, Optional

import config
from utils import run_command

try:
    # Reuse the terse-nmcli splitter (handles escaped ':' in SSIDs).
    from network import _nmcli_split
except Exception:  # pragma: no cover - network import should always succeed
    def _nmcli_split(line: str) -> List[str]:
        return line.split(':')


# Provisioning phases — also the strings reported to the portal / frontends.
PHASE_IDLE = "idle"
PHASE_AP = "ap_up"
PHASE_STOPPING_AP = "stopping_ap"
PHASE_CONNECTING = "connecting"
PHASE_VERIFYING = "verifying"
PHASE_CONNECTED = "connected"
PHASE_FAILED = "failed"


class APHandler:
    """Controls the setup-AP lifecycle and the AP->STA handoff."""

    def __init__(self):
        self._lock = threading.Lock()
        self.phase = PHASE_IDLE
        self.detail = ""
        self.last_error = ""
        self.sta_ip: Optional[str] = None
        self.sta_ssid: Optional[str] = None

    # ------------------------------------------------------------------ service
    def start_ap(self) -> bool:
        """Raise the AP (systemctl start). Idempotent."""
        ret, _, err = run_command(['systemctl', 'start', config.AP_SERVICE], check=False)
        if ret == 0:
            self.phase = PHASE_AP
            return True
        self.last_error = (err or "").strip() or "failed to start the access point"
        return False

    def stop_ap(self) -> bool:
        """Tear the AP down (systemctl stop). ExecStopPost hands the radio to NM."""
        ret, _, _ = run_command(['systemctl', 'stop', config.AP_SERVICE], check=False)
        return ret == 0

    def is_ap_active(self) -> bool:
        _, out, _ = run_command(['systemctl', 'is-active', config.AP_SERVICE], check=False)
        return out.strip() == 'active'

    # ------------------------------------------------------------- runtime info
    def read_creds(self) -> Dict[str, str]:
        """Parse /run/jrescue/ap-creds.txt (SSID=/PSK=/ADDR=/URL=)."""
        creds: Dict[str, str] = {}
        try:
            with open(config.AP_CREDS_FILE) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        creds[key.lower()] = value
        except OSError:
            pass
        return creds

    def read_scan_cache(self) -> List[dict]:
        """WiFi networks scanned BEFORE the AP took the radio.

        The single radio can't rescan while hostapd holds it, so the portal
        shows this cached list (written by jrescue-netdecide at boot).
        """
        networks: List[dict] = []
        seen = set()
        try:
            with open(config.AP_SCAN_CACHE) as f:
                lines = f.read().strip().split('\n')
        except OSError:
            return networks
        for line in lines:
            if not line:
                continue
            fields = _nmcli_split(line)
            if len(fields) < 3:
                continue
            ssid = fields[0].strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            networks.append({
                'ssid': ssid,
                'signal': fields[1].strip(),
                'security': fields[2].strip() or 'Open',
            })
        return networks

    def status(self) -> dict:
        """Everything a frontend needs to render the provisioning state."""
        creds = self.read_creds()
        return {
            'ap_active': self.is_ap_active(),
            'ssid': creds.get('ssid'),
            'psk': creds.get('psk'),
            'url': creds.get('url', config.AP_URL),
            'address': creds.get('addr', config.AP_ADDR),
            'mdns': config.MDNS_HOSTNAME,
            'phase': self.phase,
            'detail': self.detail,
            'error': self.last_error,
            'sta_ip': self.sta_ip,
            'sta_ssid': self.sta_ssid,
        }

    # ----------------------------------------------------------------- helpers
    def _wifi_iface(self) -> Optional[str]:
        """The Wi-Fi netdev name (auto-detected; no hardcoded wlan0).

        Prefer a station-capable (`type managed`) vif from `iw dev` so a leftover
        P2P-device/monitor/AP vif is never handed to the STA connect; fall back to
        the nmcli wifi device (which also lists the radio while it's an AP).
        """
        ret, out, _ = run_command(['iw', 'dev'], check=False)
        if ret == 0 and out:
            name = None
            for line in out.split('\n'):
                s = line.strip()
                if s.startswith('Interface '):
                    name = s.split(None, 1)[1].strip()
                elif s.startswith('type ') and name:
                    if s.split(None, 1)[1].strip() == 'managed':
                        return name
                    name = None  # not a station vif — keep looking
        # Fallback via nmcli (lists the wifi device even while it's an AP).
        ret, out, _ = run_command(
            ['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'], check=False)
        if ret == 0 and out:
            for line in out.strip().split('\n'):
                fields = _nmcli_split(line)
                if len(fields) >= 2 and fields[1] == 'wifi':
                    return fields[0]
        return None

    def _wait_wifi_managed(self, iface: Optional[str], timeout: float = 6.0) -> None:
        """After stopping the AP, wait for NM to re-own the Wi-Fi device.

        The AP left the radio `managed no`; jrescue-ap-down set it back to
        `managed yes`, but the driver needs a moment to drop AP mode before NM /
        wpa_supplicant can drive it as an STA.
        """
        if not iface:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, out, _ = run_command(
                ['nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status'], check=False)
            for line in (out or '').strip().split('\n'):
                fields = _nmcli_split(line)
                if (len(fields) >= 2 and fields[0] == iface
                        and fields[1] not in ('unmanaged', 'unavailable')):
                    return
            time.sleep(0.5)

    def _default_gateway(self) -> Optional[str]:
        ret, out, _ = run_command(['ip', 'route', 'show', 'default'], check=False)
        if ret == 0 and out:
            parts = out.split()
            if len(parts) >= 3 and parts[0] == 'default':
                return parts[2]
        return None

    def _online(self, timeout: float = 15.0) -> bool:
        """Success criterion: a default route exists AND something answers.

        Prefer pinging the gateway, but a gateway that silently drops ICMP must
        not fail a working connection — fall back to a TCP connect to the JetHome
        API. A missing default route always fails (association without a usable
        network is not success).
        """
        import socket

        deadline = time.time() + timeout
        while time.time() < deadline:
            gateway = self._default_gateway()
            if gateway:
                ret, _, _ = run_command(
                    ['ping', '-c', '1', '-W', '2', gateway], check=False)
                if ret == 0:
                    return True
                # Gateway present but ICMP-silent — try to actually reach the API.
                try:
                    with socket.create_connection(('fw.jethome.com', 443), timeout=3):
                        return True
                except OSError:
                    pass
            time.sleep(2)
        return False

    def _current_ip(self, iface: str) -> Optional[str]:
        ret, out, _ = run_command(
            ['nmcli', '-t', '-f', 'IP4.ADDRESS', 'device', 'show', iface], check=False)
        if ret == 0 and out:
            first = out.strip().split('\n')[0]
            fields = _nmcli_split(first)
            if len(fields) >= 2 and fields[1]:
                return fields[1].split('/')[0]
        return None

    # ----------------------------------------------------------------- handoff
    def provision(self, ssid: str, password: str = None,
                  progress_cb: Optional[Callable[[str, str], None]] = None) -> dict:
        """Join <ssid>, tearing the AP down first; roll back to the AP on failure.

        Returns {'ok': bool, 'ip': str|None, 'error': str}. Serialised: only one
        handoff may touch the single radio at a time.
        """
        def emit(phase: str, detail: str = "") -> None:
            self.phase = phase
            self.detail = detail
            if progress_cb:
                try:
                    progress_cb(phase, detail)
                except Exception:
                    pass

        if not self._lock.acquire(blocking=False):
            return {'ok': False, 'ip': None, 'error': 'provisioning already in progress'}
        try:
            self.last_error = ""
            self.sta_ip = None
            self.sta_ssid = None

            if not ssid:
                emit(PHASE_FAILED, "no network selected")
                self.last_error = "no network selected"
                return {'ok': False, 'ip': None, 'error': self.last_error}

            # 1. AP_DOWN — release the single radio.
            emit(PHASE_STOPPING_AP, "Stopping access point")
            self.stop_ap()
            iface = self._wifi_iface()
            self._wait_wifi_managed(iface)

            # 2. STA_TRYING — associate + DHCP (nmcli blocks until done / 45s).
            emit(PHASE_CONNECTING, "Joining %s" % ssid)
            cmd = ['nmcli', '--wait', '45', 'device', 'wifi', 'connect', ssid]
            if password:
                cmd += ['password', password]
            if iface:
                cmd += ['ifname', iface]
            ret, out, err = run_command(cmd, check=False)
            if ret != 0:
                reason = (err or out or "could not join the network").strip()
                return self._rollback(ssid, reason, emit)

            # 3. VERIFYING — real connectivity is an IP AND a usable default route.
            emit(PHASE_VERIFYING, "Verifying connection")
            if not iface:
                iface = self._wifi_iface()  # device may have finished enumerating
            ip = self._current_ip(iface) if iface else None
            if not ip:
                time.sleep(2)  # give DHCP a beat
                ip = self._current_ip(iface) if iface else None
            if not ip or not self._online():
                return self._rollback(
                    ssid, "joined but no route to the network", emit)

            # 4. CONNECTED — AP stays down; STA is now the only network.
            self.sta_ip = ip
            self.sta_ssid = ssid
            emit(PHASE_CONNECTED, "Connected to %s" % ssid)
            return {'ok': True, 'ip': ip, 'error': ''}
        finally:
            self._lock.release()

    def _rollback(self, ssid: str, reason: str,
                  emit: Callable[[str, str], None]) -> dict:
        """Drop the failed profile and re-raise the AP so the user can retry."""
        # Delete the just-created profile so a wrong password doesn't linger and
        # auto-reconnect (which would hold the radio away from a fresh attempt).
        run_command(['nmcli', 'connection', 'delete', ssid], check=False)
        self.last_error = reason
        self.start_ap()
        emit(PHASE_FAILED, reason)
        return {'ok': False, 'ip': None, 'error': reason}


# Module-level singleton so every frontend shares one provisioning state.
_ap_handler: Optional[APHandler] = None


def get_ap_handler() -> APHandler:
    global _ap_handler
    if _ap_handler is None:
        _ap_handler = APHandler()
    return _ap_handler
