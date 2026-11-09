"""Read recovery/device facts without mounting filesystems or writing storage."""

import fcntl
import os
from pathlib import Path
import re
import shlex
import struct

import config


def _text(path):
    """Treat missing hardware/proc entries as unavailable information."""
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace').replace('\0', '').strip()
    except OSError:
        return ''


def _number(path):
    """Read a nonnegative sysfs integer."""
    try:
        value = int(_text(path))
        return value if value >= 0 else None
    except ValueError:
        return None


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


def _crc32c(data):
    """Use ext4's initial CRC and polynomial, without a final XOR."""
    crc = 0xffffffff
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc


def ext_space(superblock, extent_size):
    """Read matched (total, available) ext2/3/4 sizes with validated counters.

    An offline value is only an estimate: journal replay may change it. The
    caller never mounts or replays the installed OS filesystem.
    """
    if len(superblock) != 1024 or struct.unpack_from('<H', superblock, 0x38)[0] != 0xef53:
        return None
    log_size = struct.unpack_from('<I', superblock, 0x18)[0]
    incompat, ro_compat = struct.unpack_from('<II', superblock, 0x60)
    if log_size > 6 or ro_compat & 0x200 or struct.unpack_from('<H', superblock, 0x3a)[0] & 2:
        return None
    if ro_compat & 0x400:
        if superblock[0x175] != 1 or _crc32c(superblock[:0x3fc]) != struct.unpack_from('<I', superblock, 0x3fc)[0]:
            return None
    total, reserved, free = struct.unpack_from('<III', superblock, 0x4)
    if incompat & 0x80:
        high = struct.unpack_from('<III', superblock, 0x150)
        total, reserved, free = (low+(upper << 32) for low, upper in zip((total, reserved, free), high))
    block_size = 1024 << log_size
    if not total or total*block_size > extent_size or free > total or reserved > total:
        return None
    return total*block_size, max(0, free-reserved)*block_size


def ext_free_space(superblock, extent_size):
    """Keep the available-space accessor consistent with validated FS totals."""
    space = ext_space(superblock, extent_size)
    return space[1] if space is not None else None


def _mounts(root):
    """Match mounted filesystems by device number, excluding the RAM rootfs."""
    mounted = {}
    for line in _text(root/'proc/self/mountinfo').splitlines():
        fields = line.split()
        if len(fields) < 6:
            continue
        path = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), fields[4])
        mounted[fields[2]] = root/path.lstrip('/')
    return mounted


def _emmc_usage(root):
    """Inspect the largest eMMC partition; never substitute RAM or boot free space."""
    result = {'total': None, 'filesystem_total': None, 'free': None,
              'approximate': False, 'busy': False}
    block_root = root/'sys/class/block'
    try:
        devices = sorted(p for p in block_root.glob('mmcblk*')
                         if re.fullmatch(r'mmcblk\d+', p.name) and _text(p/'device/type') == 'MMC')
    except OSError:
        return result
    if not devices:
        return result
    preferred = Path(config.EMMC_DEVICE).name
    device = next((p for p in devices if p.name == preferred), devices[0])
    sectors = _number(device/'size')
    if not sectors:
        return result
    result['total'] = sectors*512
    try:
        partitions = [p for p in block_root.glob(device.name+'p*')
                      if re.fullmatch(re.escape(device.name)+r'p\d+', p.name)]
    except OSError:
        return result
    extents = []
    for part in partitions:
        start, size = _number(part/'start'), _number(part/'size')
        if start is None or not size or start+size > sectors:
            return result
        extents.append((size*512, start*512, part))
    if not partitions:
        extents = [(sectors*512, 0, device)]
    if not extents:
        return result
    size, start, part = max(extents, key=lambda item: item[0])
    try:
        with open(root/'dev'/device.name, 'rb', buffering=0) as source:
            # The image writer takes an exclusive lock on this same device.
            fcntl.flock(source, fcntl.LOCK_SH | fcntl.LOCK_NB)
            mountpoint = _mounts(root).get(_text(part/'dev'))
            if mountpoint is not None:
                descriptor = os.open(mountpoint, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    # Pin and verify the mount: an unmount must not make this
                    # directory report the recovery RAM filesystem's free space.
                    identity = os.fstat(descriptor).st_dev
                    if '{}:{}'.format(os.major(identity), os.minor(identity)) == _text(part/'dev'):
                        stat = os.fstatvfs(descriptor)
                        unit = stat.f_frsize or stat.f_bsize
                        total, free = stat.f_blocks*unit, stat.f_bavail*unit
                        if 0 <= free <= total <= size and total:
                            result['filesystem_total'] = total
                            result['free'] = free
                finally:
                    os.close(descriptor)
            elif size >= 2048:
                source.seek(start+1024)
                space = ext_space(source.read(1024), size)
                if space is not None:
                    result['filesystem_total'], result['free'] = space
                    result['approximate'] = True
    except BlockingIOError:
        result['busy'] = True
    except (OSError, ValueError):
        pass
    return result


def get_recovery_info(root='/'):
    """Collect a snapshot for Info; an alternate root supports isolated fixtures."""
    root = Path(root)
    memory = {}
    for line in _text(root/'proc/meminfo').splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] in ('MemTotal:', 'MemAvailable:', 'MemFree:'):
            try:
                memory[fields[0][:-1]] = max(0, int(fields[1]))*1024
            except ValueError:
                pass
    total = memory.get('MemTotal')
    available = memory.get('MemAvailable', memory.get('MemFree'))
    if total is not None and available is not None:
        available = min(available, total)
    release = _os_release(root)
    firmware = release.get('PRETTY_NAME') or ' '.join(
        release.get(key, '') for key in ('NAME', 'VERSION_ID')).strip()
    return {
        'model': _text(root/'proc/device-tree/model') or config.JETHOME_DEVICE_NAME,
        'ram_total': total, 'ram_available': available, 'emmc': _emmc_usage(root),
        'firmware': firmware or None, 'app_version': config.APP_VERSION,
    }
