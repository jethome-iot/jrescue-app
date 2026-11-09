"""
Flash Image Screen for OLED
"""

import sys
import os

# Add parent dir to path for language import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t

# Add core/ to path to reuse modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from download import DownloadHandler
from flash import FlashHandler
from usb import USBHandler
import config as src_config
from .reboot import reboot_after_flash


def _hold_confirmation(menu, action, detail='', title=''):
    """Use reboot's physical guard; let callers clean RAM before error dialogs."""
    try:
        return menu.hold_to_confirm(title, action, detail, seconds=3.0,
                                    plain_title=bool(title)), None
    except (OSError, RuntimeError):
        return None, t('reboot_input_failed')


def image_size(image):
    """Keep the download size visible without needing a separate header."""
    try:
        size = int(image['size']) if image.get('size') is not None else int(image.get('size_mb', 0))*1024**2
    except (TypeError, ValueError, OverflowError):
        return '--'
    if size <= 0:
        return '--'
    if size >= 1024**3:
        return '{:.1f} GiB'.format(size/1024**3)
    return '{} MiB'.format((size+1024**2-1)//1024**2)


def flash_menu(menu):
    """
    Flash image menu - select source

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    items = [t("flash_api"), t("flash_usb")]

    while True:
        # Use select_from_list instead of show_menu for scrolling support
        choice = menu.select_from_list(t("flash_title"), items, show_index=False,
                                       show_counter=True)

        if choice is None:
            return None  # Back
        elif choice == -1:
            return -1  # Home - go to main menu
        elif choice == 0:
            result = flash_from_http(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu
        elif choice == 1:
            result = flash_from_usb(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu


def flash_from_http(menu):
    """
    Download image from HTTP and flash

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    handler = DownloadHandler()

    images = menu.run_working(t("flash_list"), t("wait"), handler.list_available_images)

    if not images:
        result = menu.show_message(t("error"), handler.last_error or t("no_images"))
        if result == -1:
            return -1  # Home
        return None  # Back

    # Build image list (no truncation - text wraps automatically)
    image_names = []
    for img in images:
        name = img['name']
        image_names.append(name)

    # Select image (with counter to show total number of images)
    selected = menu.select_from_list(t("flash_select"), image_names, show_index=True, show_counter=True)

    if selected is None:
        return None  # Cancelled
    elif selected == -1:
        return -1  # Home

    image = images[selected]

    choice, error = _hold_confirmation(menu, t('flash_download_image'), image_size(image))
    if error:
        return menu.show_message(t('error'), error)
    if choice == -1:
        return -1  # Home
    if choice is not True:
        return None  # Cancelled

    downloaded = None

    def download(progress, cancel):
        """Use the downloader's measured bytes and report completion after rename."""
        nonlocal downloaded

        def report(percent, amount='', speed=''):
            """Use the second text row for bytes, without crowding it with speed/ETA."""
            progress(percent, amount)

        downloaded = handler.download_file(image['url'], dest_filename=image['filename'],
                                           progress_cb=report, cancel_event=cancel)
        if downloaded and not cancel.is_set():
            progress(100)
        return downloaded

    try:
        try:
            _, cancelled = menu.run_download(t("flash_downloading"), image['name'], download)
        except Exception as exc:
            if downloaded:
                handler.discard_download(downloaded)
            return menu.show_message(t('error'), str(exc))
        if cancelled is not None:
            return -1 if cancelled == -1 else None
        if not downloaded:
            return menu.show_message(t("error"), handler.last_error or t("download_failed"))

        image_name = image.get('name', image.get('filename', 'Image'))
        if menu.show_message(t("flash_downloaded"), image_name, success=True) == -1:
            return -1
        return perform_flash(menu, downloaded, image_name,
                             cleanup=lambda: handler.discard_download(downloaded))
    finally:
        # Also handles a cancel arriving just after the final file was renamed.
        if downloaded:
            handler.discard_download(downloaded)


def flash_from_usb(menu):
    """
    Load image from USB and flash

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    usb_handler = USBHandler()

    # Detect USB devices
    devices = menu.run_working(t("usb_title"), t("usb_detecting"),
                               usb_handler.detect_usb_devices)

    if not devices:
        # Show info message (not an error - USB simply not connected)
        result = menu.show_message(t("info"), t("usb_no_device"))
        if result == -1:
            return -1  # Home
        return None  # Back

    # Mount device if needed
    device = devices[0]  # Use first device

    if not device['mountpoint']:
        if not menu.run_working(t("usb_title"), t("usb_mounting"),
                                usb_handler.mount_device, device['device']):
            result = menu.show_message(t("error"), t("usb_mount_failed"))
            if result == -1:
                return -1  # Home
            return None  # Back
        mount_point = usb_handler.mount_point
    else:
        mount_point = device['mountpoint']

    # Scan for images
    images = menu.run_working(t("usb_title"), t("usb_scanning"),
                              usb_handler.scan_for_images, mount_point)

    if not images:
        result = menu.show_message(t("info"), t("usb_no_images"))
        if not device['mountpoint']:
            usb_handler.unmount_device()
        if result == -1:
            return -1  # Home
        return None  # Back

    # Select image (with counter to show total number of images)
    image_names = [img['filename'] for img in images]
    selected = menu.select_from_list(t("usb_images"), image_names, show_index=True, show_counter=True)

    if selected is None:
        if not device['mountpoint']:
            usb_handler.unmount_device()
        return None  # Cancelled
    elif selected == -1:
        if not device['mountpoint']:
            usb_handler.unmount_device()
        return -1  # Home

    image_path = images[selected]['path']

    # Flash
    result = perform_flash(menu, image_path)

    # Unmount if we mounted it
    if not device['mountpoint']:
        usb_handler.unmount_device()

    if result == -1:
        return -1  # Propagate HOME to main menu
    elif result:
        menu.show_message(t("info"), t("usb_safe_remove"))


def perform_flash(menu, image_path, image_name=None, cleanup=None):
    """
    Perform the actual flash operation

    Args:
        menu: Menu instance
        image_path: Path to image file

    Returns:
        -1 if HOME pressed, None otherwise
    """
    failure = None
    try:
        warning = t('flash_warning').split('\n', 1)
        choice, failure = _hold_confirmation(menu, warning[0], warning[1],
                                              title=t('flash_write_image'))
        if failure is None:
            if choice == -1:
                return -1
            if choice is not True:
                return None

            flash_handler = FlashHandler(emmc_device=src_config.EMMC_DEVICE)

            def write(progress):
                """Show measured progress without repeating the target device name."""
                def report(percent, name='', detail=''):
                    progress(percent, '' if str(detail).startswith('/dev/') else detail)

                return flash_handler.flash_image(
                    image_path, skip_confirmation=True,
                    progress_cb=report)

            try:
                success = menu.run_progress(
                    t("flash_progress"), image_name or os.path.basename(image_path), write)
            except Exception as exc:
                failure = str(exc)
    finally:
        # Release RAM before any completion/reboot dialog can wait for input.
        if cleanup:
            cleanup()

    if failure is not None:
        return menu.show_message(t("error"), failure)
    if success:
        result = menu.show_message(t("flash_complete"), image_name or os.path.basename(image_path),
                                   success=True)
        if result == -1:
            return -1  # Home

        return reboot_after_flash(menu)
    else:
        result = menu.show_message(t("error"), t("flash_failed"))
        if result == -1:
            return -1  # Home
        return None
