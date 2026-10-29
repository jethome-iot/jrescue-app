"""Fast cleanup of downloaded RAM images, coordinated with active readers."""

import contextlib
import fcntl
import os


def is_cached_image(path, directory):
    """Accept image files directly inside the cache, never prefix-matching siblings."""
    path = os.path.abspath(path)
    return (os.path.realpath(os.path.dirname(path)) == os.path.realpath(directory) and
            os.path.basename(path).lower().endswith(('.img', '.xz', '.partial')))


@contextlib.contextmanager
def cache_lock(directory, exclusive=True):
    """Fail quickly instead of cleaning an image still used by another frontend."""
    directory = os.path.abspath(directory)
    if directory in ('/', '/tmp') or os.path.islink(directory):
        raise ValueError('A dedicated image cache directory is required')
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, '.images.lock'), 'a+b') as lock:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(lock, mode | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('An image download or flash is already using the RAM cache')
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def clear_images_unlocked(directory):
    """Unlink old images and partials without reading their data or recursing.

    The caller must hold the exclusive cache lock. Symlinks are unlinked as
    directory entries; their targets, including any USB files, stay untouched.
    """
    with os.scandir(directory) as entries:
        for entry in entries:
            if is_cached_image(entry.path, directory) and not entry.is_dir(follow_symlinks=False):
                try:
                    os.unlink(entry.path)
                except FileNotFoundError:
                    pass


def image_identity(path):
    """Identify the completed download without retaining an open RAM file."""
    stat = os.stat(path, follow_symlinks=False)
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def discard_image(path, directory, expected=None):
    """Remove only a cached image, optionally checking that it has not been replaced."""
    if not is_cached_image(path, directory):
        raise ValueError('Image is outside the download cache')
    with cache_lock(directory):
        try:
            if expected is None or image_identity(path) == expected:
                os.unlink(path)
        except FileNotFoundError:
            pass


@contextlib.contextmanager
def cached_image_reader(path, directory):
    """Protect cached flash sources from cleanup; leave USB images independent."""
    if is_cached_image(path, directory):
        with cache_lock(directory, exclusive=False):
            yield
    else:
        yield
