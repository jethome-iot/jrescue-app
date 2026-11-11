"""Read recovery identity and an optional snapshot of total RAM/eMMC capacity."""

from pathlib import Path
import re
import shlex

import config


def _text(path):
    """Treat missing hardware/proc entries as unavailable information."""
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace').replace('\0', '').strip()
    except OSError:
        return ''


def _os_release(root):
    """Parse os-release as data, never as shell commands."""
    data = {}
    source = _text(root/'etc/os-release') or _text(root/'usr/lib/os-release')
    for line in source.splitlines():
        key, separator, value = line.partition('=')
        if not separator or key.startswith('#'):
            continue
        try:
            data[key.strip()] = ' '.join(shlex.split(value, comments=True))
        except ValueError:
            continue
    return data


def get_recovery_info(root='/'):
    """Collect a snapshot for Info; an alternate root supports isolated fixtures."""
    root = Path(root)
    release = _os_release(root)
    firmware = release.get('PRETTY_NAME') or ' '.join(
        release.get(key, '') for key in ('NAME', 'VERSION_ID')).strip()
    return {
        'model': _text(root/'proc/device-tree/model') or config.JETHOME_DEVICE_NAME,
        'firmware': firmware or None,
    }


def get_memory_info(root='/'):
    """Read total RAM and the eMMC user area without mounting or opening disks."""
    root = Path(root)
    ram = None
    for line in _text(root/'proc/meminfo').splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] == 'MemTotal:' and fields[2] == 'kB':
            try:
                value = int(fields[1])*1024
                ram = value if value > 0 else None
            except ValueError:
                pass
            break
    devices = []
    try:
        for path in (root/'sys/block').iterdir():
            if re.fullmatch(r'mmcblk\d+', path.name) and _text(path/'device/type') == 'MMC':
                devices.append(path)
    except OSError:
        pass
    preferred = Path(config.EMMC_DEVICE).name
    target = next((path for path in devices if path.name == preferred), None)
    if target is None and len(devices) == 1:
        target = devices[0]
    emmc = None
    if target is not None:
        try:
            # Linux reports this field in 512-byte sectors, independent of
            # the device's logical/physical block size.
            value = int(_text(target/'size'))*512
            emmc = value if value > 0 else None
        except ValueError:
            pass
    return {'ram_total': ram, 'emmc_total': emmc}
