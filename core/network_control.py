"""Serialize network changes and restart existing links without deleting profiles."""

import contextlib
import fcntl
import os
import uuid

import config
from utils import check_command_exists, run_command


class NetworkBusyError(RuntimeError):
    """Another frontend is changing the network or provisioning Wi-Fi."""


@contextlib.contextmanager
def network_change_lock():
    """Coordinate restarts with provisioning across frontend processes."""
    os.makedirs(os.path.dirname(config.NETWORK_CONTROL_LOCK), exist_ok=True)
    with open(config.NETWORK_CONTROL_LOCK, 'a+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise NetworkBusyError('Network operation in progress')
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _command(cmd, timeout=10):
    """Keep every service and nmcli call bounded; return structured failures."""
    code, out, error = run_command(cmd, check=False, timeout=timeout)
    if code:
        if code == -1:
            raise RuntimeError('timeout')
        if cmd[0] == 'nmcli':
            from network import classify_wifi_error
            reason = classify_wifi_error(error or out, returncode=code)
            if reason != 'unknown':
                raise RuntimeError(reason)
        raise RuntimeError('failed')
    return out


def _ap_active():
    """Only restore an AP that was already running, never raise one from idle."""
    code, out, _ = run_command(['systemctl', 'is-active', config.AP_SERVICE], check=False, timeout=5)
    if code == 3 and out.strip() in ('activating', 'deactivating', 'reloading'):
        raise RuntimeError('busy')
    if code not in (0, 3) or (code == 0 and out.strip() != 'active'):
        raise RuntimeError('unavailable')
    return code == 0


def _devices():
    """Discover device names without relying on wlan0 or eth0 fallbacks."""
    from network import _nmcli_split
    result = []
    for line in _command(['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status']).splitlines():
        fields = _nmcli_split(line)
        if len(fields) >= 2 and fields[1] in ('wifi', 'ethernet'):
            result.append((fields[0], fields[1]))
    return result


def _profile(device):
    """Capture the active UUID rather than assuming a profile name is an SSID."""
    value = _command(['nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', device], timeout=5).strip()
    if not value or value == '--':
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise RuntimeError('unavailable')


def _connect(device, profile):
    """Reuse the exact active profile, including its saved credentials/static IP."""
    command = (['connection', 'up', 'uuid', profile, 'ifname', device] if profile else
               ['device', 'connect', device])
    _command(['nmcli', '--wait', '30']+command, timeout=35)


def _restore_ap():
    """AP service owns unmanaged mode, addresses, hostapd and dnsmasq cleanup."""
    _command(['systemctl', 'reset-failed', config.AP_SERVICE])
    _command(['systemctl', 'restart', config.AP_SERVICE], timeout=40)
    if not _ap_active():
        raise RuntimeError('failed')


def _restart_links(kind):
    """Reconnect adapters of one kind, or restart the already-active setup AP."""
    if kind == 'wifi' and _ap_active():
        _restore_ap()
        return
    devices = [name for name, device_kind in _devices() if device_kind == kind]
    if not devices:
        raise RuntimeError('no_device')
    profiles = [(device, _profile(device)) for device in devices]
    for device, profile in profiles:
        if profile:
            # A timed-out disconnect may still have taken effect. Always try
            # to bring the captured profile back before reporting the outcome.
            run_command(['nmcli', '--wait', '10', 'device', 'disconnect', device],
                        check=False, timeout=15)
        _connect(device, profile)


def _restart_manager():
    """Restore AP ownership after NM restarts and reapply previously active UUIDs."""
    ap_active = _ap_active()
    profiles = []
    try:
        devices = _devices()
    except RuntimeError:
        # A stopped/wedged NetworkManager is itself a reason to use this action.
        devices = []
    for name, kind in devices:
        if ap_active and kind == 'wifi':
            continue
        try:
            profiles.append((name, _profile(name)))
        except RuntimeError:
            continue
    failure = None
    try:
        if ap_active:
            _command(['systemctl', 'stop', config.AP_SERVICE], timeout=30)
        try:
            _command(['systemctl', 'restart', 'NetworkManager.service'], timeout=40)
        except (OSError, RuntimeError) as error:
            # A timed-out service job may still finish. Try every captured
            # connection before reporting failure, rather than abandoning links.
            failure = error
        for name, profile in profiles:
            if profile:
                try:
                    _connect(name, profile)
                except (OSError, RuntimeError) as error:
                    if failure is None:
                        failure = error
    finally:
        if ap_active:
            _restore_ap()
    if failure is not None:
        raise failure


def restart_network(kind):
    """Run one approved action; return codes only, never localized UI text."""
    if kind not in ('wifi', 'ethernet', 'manager'):
        return {'ok': False, 'error': 'invalid'}
    try:
        with network_change_lock():
            if not check_command_exists('nmcli'):
                return {'ok': False, 'error': 'unavailable'}
            if kind == 'manager':
                _restart_manager()
            else:
                _restart_links(kind)
    except NetworkBusyError:
        return {'ok': False, 'error': 'busy'}
    except OSError:
        return {'ok': False, 'error': 'unavailable'}
    except RuntimeError as error:
        return {'ok': False, 'error': str(error)}
    return {'ok': True, 'error': ''}
