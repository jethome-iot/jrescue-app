"""
Wi-Fi setup-AP provisioning — the "connect me to your home Wi-Fi" flow.

On a board with no wired network the recovery raises its own Wi-Fi Access Point
(hostapd + dnsmasq, driven by the system unit jrescue-ap.service). A phone joins
that AP and, through the web portal, picks the home Wi-Fi and enters its
password. This module owns the AP<->STA *policy*: it stops the AP, joins the
chosen network, verifies real connectivity (an IP *and* a reachable gateway)
and — only on failure — rolls back to the AP so the user can retry.

The radio is single (see AGENTS.md / the driver notes): it is either an AP or an
STA, never both — AP+STA concurrency is compiled out of the RTL8821CU vendor
driver. Provisioning is therefore strictly sequential and the phone WILL be
disconnected the instant the AP is stopped, so a wrong password cannot be tested
without that outage. What we CAN do is reject hopeless credentials before ever
touching the radio (preflight()), keep the outage short, and remember why an
attempt failed so the portal can explain it when the user rejoins the AP.

System vs app split: the shell side (usr/bin/jrescue-ap-up / jrescue-ap-down,
started via systemctl) owns the radio primitives — hostapd, dnsmasq, the gateway
IP, handing the device back to NetworkManager. This module never execs
hostapd/dnsmasq; it only start/stops the service and drives the nmcli-connect
handoff. The two halves talk through systemctl and the runtime files in
/run/jrescue/ (ap-creds.txt, wifi-scan.txt, provision-state.json).
"""

import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import config
from utils import run_command
from network_control import NetworkBusyError, network_change_lock

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

# Failure codes. ap.py never renders user-facing prose — it returns one of these
# and each frontend translates it (console/OLED via translations, portal via its
# own table), so the same diagnosis reads correctly in every language.
ERR_NONE = ""
ERR_NO_SSID = "no_ssid"
ERR_BAD_SSID = "bad_ssid"
ERR_ENTERPRISE = "enterprise"                    # preflight, radio untouched
ERR_WEP = "wep"                                  # preflight
ERR_NO_PASSWORD = "no_password"                  # preflight
ERR_BAD_PASSWORD_FORMAT = "bad_password_format"  # preflight
ERR_WRONG_PASSWORD = "wrong_password"
ERR_NOT_FOUND = "not_found"
ERR_NO_DHCP = "no_dhcp"
ERR_NO_INTERNET = "no_internet"
ERR_TIMEOUT = "timeout"
ERR_RADIO_BUSY = "radio_busy"
ERR_BUSY = "busy"
ERR_UNKNOWN = "unknown"

# Substrings of NetworkManager's stable wording -> code. Matched lowercase and in
# order, most-actionable first; "timeout" is last because it is the weakest
# signal and co-occurs with the real ones.
_NMCLI_ERRORS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("secrets were required", "no-secrets", "802.1x supplicant"), ERR_WRONG_PASSWORD),
    (("no network with ssid", "ssid-not-found", "could not be found"), ERR_NOT_FOUND),
    (("ip configuration could not be reserved", "ip-config", "dhcp"), ERR_NO_DHCP),
    (("strictly unmanaged", "not managed", "device is not"), ERR_RADIO_BUSY),
    (("timeout", "timed out"), ERR_TIMEOUT),
)


def classify_nmcli_error(text: str) -> str:
    """Map raw nmcli/NM output to one of the ERR_* codes."""
    low = (text or "").lower()
    for needles, code in _NMCLI_ERRORS:
        for needle in needles:
            if needle in low:
                return code
    return ERR_UNKNOWN


class APHandler:
    """Controls the setup-AP lifecycle and the AP->STA handoff."""

    def __init__(self):
        self._lock = threading.Lock()
        self.phase = PHASE_IDLE
        self.detail = ""
        self.last_error = ""
        self.last_error_code = ERR_NONE
        self.last_ssid: Optional[str] = None
        self.sta_ip: Optional[str] = None
        self.sta_ssid: Optional[str] = None
        self._load_state()

    # ------------------------------------------------------- persisted outcome
    # The console, the OLED app and the web app are separate processes with their
    # own singleton, and jrescue-web restarts on failure — so the last outcome
    # lives in a tmpfs file (gone on reboot, which is the right lifetime).
    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(config.AP_STATE_FILE), exist_ok=True)
            with open(config.AP_STATE_FILE, 'w') as f:
                json.dump({
                    'phase': self.phase,
                    'error': self.last_error,
                    'error_code': self.last_error_code,
                    'last_ssid': self.last_ssid,
                    'sta_ip': self.sta_ip,
                    'sta_ssid': self.sta_ssid,
                }, f)
        except Exception:
            pass

    def _load_state(self) -> None:
        try:
            with open(config.AP_STATE_FILE) as f:
                data = json.load(f)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        self.phase = data.get('phase') or self.phase
        self.last_error = data.get('error') or ""
        self.last_error_code = data.get('error_code') or ERR_NONE
        self.last_ssid = data.get('last_ssid')
        self.sta_ip = data.get('sta_ip')
        self.sta_ssid = data.get('sta_ssid')

    def clear_error(self) -> None:
        """Forget the last failure (the user acknowledged it in the portal)."""
        self.last_error = ""
        self.last_error_code = ERR_NONE
        if self.phase == PHASE_FAILED:
            self.phase = PHASE_AP if self.is_ap_active() else PHASE_IDLE
        self._save_state()

    # ------------------------------------------------------------------ service
    def start_ap(self) -> bool:
        """Raise the AP (systemctl start). Idempotent.

        Retries once through `systemctl reset-failed`: the unit carries a
        StartLimitBurst and every provisioning attempt cycles it, so a few quick
        retries can trip the limit — and a refused start would leave the user
        with no AP and no UI at all.
        """
        ret, _, err = run_command(['systemctl', 'start', config.AP_SERVICE],
                                  check=False, timeout=30)
        if ret == 0:
            self.phase = PHASE_AP
            return True
        run_command(['systemctl', 'reset-failed', config.AP_SERVICE],
                    check=False, timeout=10)
        ret, _, err2 = run_command(['systemctl', 'start', config.AP_SERVICE],
                                   check=False, timeout=30)
        if ret == 0:
            self.phase = PHASE_AP
            return True
        return False

    def stop_ap(self) -> bool:
        """Tear the AP down (systemctl stop). ExecStopPost hands the radio to NM."""
        ret, _, _ = run_command(['systemctl', 'stop', config.AP_SERVICE],
                                check=False, timeout=30)
        return ret == 0

    def is_ap_active(self) -> bool:
        _, out, _ = run_command(['systemctl', 'is-active', config.AP_SERVICE],
                                check=False, timeout=10)
        return out.strip() == 'active'

    def release_radio(self, timeout: float = 10.0) -> bool:
        """Free the Wi-Fi device from the AP so it can be used as a station.

        The radio is single: while jrescue-ap.service holds it (hostapd, and the
        device set `managed no`) NetworkManager cannot scan or associate, so any
        STA action from any frontend — console Wi-Fi setup, OLED, the portal
        handoff — must release it first. Returns True if an AP was stopped.
        """
        if not self.is_ap_active():
            return False
        self.stop_ap()
        self._wait_wifi_managed(self._wifi_iface(), timeout)
        self.phase = PHASE_IDLE
        return True

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

        The single radio can't rescan while hostapd holds it, so the portal shows
        this cached list (written by jrescue-netdecide at boot). Tolerates both
        the old 3-field and the newer 7-field cache (a running device may still
        hold a cache written by an older image).
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
            security = fields[2].strip() or 'Open'
            entry = {
                'ssid': ssid,
                'signal': fields[1].strip(),
                'security': security,
                'kind': _security_kind(security),
            }
            if len(fields) >= 6:
                entry['chan'] = fields[5].strip()
            networks.append(entry)
        return networks

    def _scan_entry(self, ssid: str) -> Optional[dict]:
        for net in self.read_scan_cache():
            if net['ssid'] == ssid:
                return net
        return None

    def status(self) -> dict:
        """Everything a frontend needs to render the provisioning state."""
        creds = self.read_creds()
        # Another process (the web app) may have provisioned since we started;
        # pick up its outcome so console/OLED can report it too.
        if self.phase in (PHASE_IDLE, PHASE_AP):
            self._load_state()
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
            'error_code': self.last_error_code,
            'failed': self.phase == PHASE_FAILED,
            'last_ssid': self.last_ssid,
            'sta_ip': self.sta_ip,
            'sta_ssid': self.sta_ssid,
            'handoff_estimate_s': config.AP_HANDOFF_ESTIMATE_S,
        }

    # --------------------------------------------------------------- preflight
    def preflight(self, ssid: str, password: str = None) -> Optional[Tuple[str, str]]:
        """Reject hopeless credentials WITHOUT touching the radio.

        This is the only honest form of "check before dropping the AP": a WPA2
        passphrase itself can only be proven by the 4-way handshake, but every
        input that cannot possibly work is caught here at zero cost to the user's
        connection. Returns (code, raw_reason) on rejection, None if plausible.
        """
        if not ssid:
            return ERR_NO_SSID, "no network selected"
        if len(ssid.encode('utf-8', 'replace')) > 32:
            return ERR_BAD_SSID, "network name is longer than 32 bytes"
        if any(c in ssid for c in ('\n', '\r')):
            return ERR_BAD_SSID, "network name contains control characters"

        entry = self._scan_entry(ssid)
        kind = entry['kind'] if entry else None

        if kind == 'enterprise':
            return ERR_ENTERPRISE, "WPA-Enterprise needs a username and certificate"
        if kind == 'wep':
            return ERR_WEP, "WEP networks are not supported"

        secured = kind in ('psk', 'sae') or (kind is None and bool(password))
        if kind == 'open':
            return None  # open network: any typed password is simply ignored
        if secured and not password:
            return ERR_NO_PASSWORD, "this network needs a password"

        if password and kind != 'sae':
            # WPA2-PSK: 8..63 ASCII chars, or exactly 64 hex (a raw PMK).
            is_hex_pmk = len(password) == 64 and all(
                c in '0123456789abcdefABCDEF' for c in password)
            if not is_hex_pmk:
                if not (8 <= len(password) <= 63):
                    return (ERR_BAD_PASSWORD_FORMAT,
                            "Wi-Fi passwords are 8-63 characters")
                if any(not (0x20 <= ord(c) <= 0x7E) for c in password):
                    # PBKDF2 over non-ASCII derives a different PMK than the
                    # router did — indistinguishable from a wrong password.
                    return (ERR_BAD_PASSWORD_FORMAT,
                            "password contains characters Wi-Fi cannot use")
        return None

    # ----------------------------------------------------------------- helpers
    def _wifi_iface(self) -> Optional[str]:
        """The Wi-Fi netdev name (auto-detected; no hardcoded wlan0).

        Prefer a station-capable (`type managed`) vif from `iw dev` so a leftover
        P2P-device/monitor/AP vif is never handed to the STA connect; fall back to
        the nmcli wifi device (which also lists the radio while it's an AP).
        """
        ret, out, _ = run_command(['iw', 'dev'], check=False, timeout=10)
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
            ['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'],
            check=False, timeout=15)
        if ret == 0 and out:
            for line in out.strip().split('\n'):
                fields = _nmcli_split(line)
                if len(fields) >= 2 and fields[1] == 'wifi':
                    return fields[0]
        return None

    def _wait_wifi_managed(self, iface: Optional[str], timeout: float = 10.0) -> None:
        """After stopping the AP, wait for NM to re-own the Wi-Fi device.

        The AP left the radio `managed no`; jrescue-ap-down set it back to
        `managed yes`, but the driver needs a moment to drop AP mode before NM /
        wpa_supplicant can drive it as an STA. Require a settled state — the
        USB RTL8821CU is slow leaving AP mode and a looser check returns while
        the driver is still transitioning.
        """
        if not iface:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, out, _ = run_command(
                ['nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status'],
                check=False, timeout=15)
            for line in (out or '').strip().split('\n'):
                fields = _nmcli_split(line)
                if (len(fields) >= 2 and fields[0] == iface
                        and fields[1] in ('disconnected', 'connected')):
                    return
            time.sleep(0.5)

    def _wait_ssid_visible(self, iface: Optional[str], ssid: str,
                           timeout: float = 12.0) -> bool:
        """Scan until the target SSID is in NM's list (or give up).

        `nmcli device wifi connect` does NOT scan — it reads NetworkManager's
        cached AP list, which is empty the instant NM re-manages a device that
        was just an AP. Without this a perfectly correct password fails
        immediately with "No network with SSID found".
        """
        deadline = time.time() + timeout
        cmd = ['nmcli', '-t', '-f', 'SSID', 'device', 'wifi', 'list', '--rescan', 'yes']
        if iface:
            cmd += ['ifname', iface]
        while time.time() < deadline:
            _, out, _ = run_command(cmd, check=False, timeout=20)
            for line in (out or '').strip().split('\n'):
                if _nmcli_split(line)[0].strip() == ssid:
                    return True
            time.sleep(1)
        return False

    def _default_gateway(self) -> Optional[str]:
        ret, out, _ = run_command(['ip', 'route', 'show', 'default'],
                                  check=False, timeout=10)
        if ret == 0 and out:
            parts = out.split()
            if len(parts) >= 3 and parts[0] == 'default':
                return parts[2]
        return None

    def _online(self, timeout: float = 10.0) -> bool:
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
                ret, _, _ = run_command(['ping', '-c', '1', '-W', '2', gateway],
                                        check=False, timeout=8)
                if ret == 0:
                    return True
                # Gateway present but ICMP-silent — try to actually reach the API.
                # Only when there is budget left: socket timeout covers the TCP
                # connect but NOT getaddrinfo, which can block for many seconds
                # on a broken resolver — and every one of those is AP downtime.
                if time.time() + 4 < deadline:
                    try:
                        with socket.create_connection(('fw.jethome.com', 443), timeout=3):
                            return True
                    except OSError:
                        pass
            time.sleep(1)
        return False

    def _current_ip(self, iface: str) -> Optional[str]:
        ret, out, _ = run_command(
            ['nmcli', '-t', '-f', 'IP4.ADDRESS', 'device', 'show', iface],
            check=False, timeout=15)
        if ret == 0 and out:
            first = out.strip().split('\n')[0]
            fields = _nmcli_split(first)
            if len(fields) >= 2 and fields[1]:
                return fields[1].split('/')[0]
        return None

    def _wait_for_ip(self, iface: Optional[str], timeout: float = 5.0) -> Optional[str]:
        if not iface:
            return None
        deadline = time.time() + timeout
        while True:
            ip = self._current_ip(iface)
            if ip or time.time() >= deadline:
                return ip
            time.sleep(0.5)

    # ----------------------------------------------------------------- handoff
    def provision(self, ssid: str, password: str = None,
                  progress_cb: Optional[Callable[[str, str], None]] = None) -> dict:
        """Keep the AP handoff exclusive against other frontends' network restarts."""
        try:
            with network_change_lock():
                return self._provision(ssid, password, progress_cb)
        except NetworkBusyError:
            return {'ok': False, 'ip': None, 'error': 'network operation in progress',
                    'error_code': ERR_BUSY}
        except OSError:
            return {'ok': False, 'ip': None, 'error': 'network control unavailable',
                    'error_code': ERR_RADIO_BUSY}

    def _provision(self, ssid: str, password: str = None,
                   progress_cb: Optional[Callable[[str, str], None]] = None) -> dict:
        """Join <ssid>, tearing the AP down first; roll back to the AP on failure.

        Returns {'ok': bool, 'ip': str|None, 'error': str, 'error_code': str}.
        Serialised: only one handoff may touch the single radio at a time.
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
            return {'ok': False, 'ip': None, 'error': 'provisioning already in progress',
                    'error_code': ERR_BUSY}
        try:
            self.last_error = ""
            self.last_error_code = ERR_NONE
            self.sta_ip = None
            self.sta_ssid = None
            self.last_ssid = ssid

            # 0. PREFLIGHT — everything checkable without the radio. A rejection
            #    here costs the user nothing: the AP is still up.
            bad = self.preflight(ssid, password)
            if bad:
                code, reason = bad
                self.last_error, self.last_error_code = reason, code
                emit(PHASE_FAILED, reason)
                self._save_state()
                return {'ok': False, 'ip': None, 'error': reason, 'error_code': code}

            # 1. AP_DOWN — release the single radio. From here the phone is gone.
            emit(PHASE_STOPPING_AP, "Stopping access point")
            self.stop_ap()
            iface = self._wifi_iface()
            self._wait_wifi_managed(iface)

            # 2. STA_TRYING — make the SSID visible first (nmcli does not scan),
            #    then associate + DHCP.
            emit(PHASE_CONNECTING, "Joining %s" % ssid)
            self._wait_ssid_visible(iface, ssid)
            cmd = ['nmcli', '--wait', '35', 'device', 'wifi', 'connect', ssid]
            if password:
                cmd += ['password', password]
            if iface:
                cmd += ['ifname', iface]
            started = time.time()
            ret, out, err = run_command(cmd, check=False, timeout=50)
            if ret != 0:
                reason = (err or out or "could not join the network").strip()
                code = classify_nmcli_error(reason)
                # "Secrets were required" is emitted both for a bad PSK and for a
                # plain association timeout — the elapsed time tells them apart.
                if code == ERR_WRONG_PASSWORD and time.time() - started >= 20:
                    code = ERR_TIMEOUT
                return self._rollback(ssid, reason, code, emit)

            # 3. VERIFYING — real connectivity is an IP AND a usable default route.
            emit(PHASE_VERIFYING, "Verifying connection")
            if not iface:
                iface = self._wifi_iface()  # device may have finished enumerating
            ip = self._wait_for_ip(iface)
            if not ip:
                return self._rollback(ssid, "joined but got no IP address",
                                      ERR_NO_DHCP, emit)
            if not self._online():
                return self._rollback(ssid, "joined but no route to the network",
                                      ERR_NO_INTERNET, emit)

            # 4. CONNECTED — AP stays down; STA is now the only network.
            self.sta_ip = ip
            self.sta_ssid = ssid
            emit(PHASE_CONNECTED, "Connected to %s" % ssid)
            self._save_state()
            return {'ok': True, 'ip': ip, 'error': '', 'error_code': ERR_NONE}
        finally:
            self._lock.release()

    def _rollback(self, ssid: str, reason: str, code: str,
                  emit: Callable[[str, str], None]) -> dict:
        """Drop the failed profile and re-raise the AP so the user can retry."""
        # Delete the just-created profile so a wrong password doesn't linger and
        # auto-reconnect (which would hold the radio away from a fresh attempt).
        run_command(['nmcli', 'connection', 'delete', 'id', ssid],
                    check=False, timeout=15)

        # Bring the AP back FIRST: start_ap() reports its own failure, and doing
        # it after we record the reason would overwrite the real cause.
        self.start_ap()

        self.last_error = reason
        self.last_error_code = code
        # Give jrescue-ap-up a moment to republish the creds so status() has the
        # SSID by the time the phone rejoins and reloads the portal.
        for _ in range(20):
            if self.read_creds().get('ssid'):
                break
            time.sleep(0.5)
        emit(PHASE_FAILED, reason)
        self._save_state()
        return {'ok': False, 'ip': None, 'error': reason, 'error_code': code}


def _security_kind(security: str) -> str:
    """Classify an nmcli SECURITY string: open|wep|psk|sae|enterprise."""
    s = (security or "").upper()
    if not s or s in ('--', 'OPEN'):
        return 'open'
    if '802.1X' in s or 'EAP' in s:
        return 'enterprise'
    if 'WEP' in s:
        return 'wep'
    if 'SAE' in s or 'WPA3' in s:
        return 'sae'
    if 'WPA' in s or 'PSK' in s or 'RSN' in s:
        return 'psk'
    return 'psk'


# Module-level singleton so every frontend shares one provisioning state.
_ap_handler: Optional[APHandler] = None


def get_ap_handler() -> APHandler:
    global _ap_handler
    if _ap_handler is None:
        _ap_handler = APHandler()
    return _ap_handler
