"""Read the device model and recovery build version without telemetry."""

from pathlib import Path
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
