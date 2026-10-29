"""Stream a disk image without writing its protected recovery window."""

import argparse
import fcntl
import os
import stat
import sys


def validate_range(protect_start: int, protect_end: int, block_size: int) -> None:
    """Reject invalid settings before opening the target for writing."""
    if any(type(value) is not int for value in (protect_start, protect_end, block_size)):
        raise ValueError("Recovery bounds and write block size must be integers")
    if (protect_start, protect_end) != (0, 0) and not 0 <= protect_start < protect_end:
        raise ValueError("Invalid recovery protection range")
    if block_size <= 0:
        raise ValueError("Image write block size must be positive")


def _write_all(target, offset: int, data) -> int:
    """Write a complete slice even when the underlying device writes short."""
    target.seek(offset)
    remaining = memoryview(data)
    size = len(remaining)
    while remaining:
        written = target.write(remaining)
        if written is None or written <= 0:
            raise OSError("Image write made no progress")
        remaining = remaining[written:]
    return size


def write_image_stream(source, target_path: str, protect_start: int,
                       protect_end: int, block_size: int,
                       progress_cb=None) -> int:
    """Write image byte X to target byte X, except [protect_start, protect_end).

    Consume the protected input too, so a pipe or XZ decoder stays aligned and
    reaches EOF for its integrity checks. Never truncate the target: seeking
    past recovery must leave the installed slots intact, including in tests
    with regular files. The device lock also serializes independent frontends.
    progress_cb, if supplied, receives (image_bytes_consumed, bytes_written).
    """
    validate_range(protect_start, protect_end, block_size)
    position = 0
    bytes_written = 0

    with open(target_path, 'r+b', buffering=0) as target:
        target_stat = os.fstat(target.fileno())
        if not (stat.S_ISBLK(target_stat.st_mode) or
                stat.S_ISREG(target_stat.st_mode)):
            raise ValueError("Image target must be a block device or regular file")
        fcntl.flock(target, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            source_stat = os.fstat(source.fileno())
        except (AttributeError, OSError, ValueError):
            source_stat = None
        if source_stat and (source_stat.st_dev, source_stat.st_ino) == (
                target_stat.st_dev, target_stat.st_ino):
            raise ValueError("Image source and target are the same file")

        while True:
            chunk = source.read(block_size)
            if not chunk:
                break
            chunk_end = position + len(chunk)
            data = memoryview(chunk)

            if position < protect_start:
                prefix_size = min(len(chunk), protect_start - position)
                bytes_written += _write_all(target, position, data[:prefix_size])
            if chunk_end > protect_end:
                suffix_start = max(0, protect_end - position)
                bytes_written += _write_all(
                    target, position + suffix_start, data[suffix_start:])

            position = chunk_end
            if progress_cb:
                progress_cb(position, bytes_written)

        if position <= protect_end:
            raise ValueError("Image contains no data after the recovery window")
        os.fsync(target.fileno())

    return bytes_written


def main() -> int:
    """Accept decoded image bytes on stdin for the pv/xz pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--protect-start', required=True, type=int)
    parser.add_argument('--protect-end', required=True, type=int)
    parser.add_argument('--block-size', required=True, type=int)
    args = parser.parse_args()
    try:
        write_image_stream(sys.stdin.buffer, args.target, args.protect_start,
                           args.protect_end, args.block_size)
    except (OSError, ValueError) as exc:
        print("Image write failed: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
