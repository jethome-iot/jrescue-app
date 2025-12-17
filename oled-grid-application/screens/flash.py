"""
Flash Image Screen for OLED
"""

import sys
import os
import time
import threading

# Add parent dir to path for language import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t

# Add core/ to path to reuse modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from download import DownloadHandler
from flash import FlashHandler
from usb import USBHandler
import config as src_config


def flash_menu(menu):
    """
    Flash image menu - select source

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    items = [t("flash_api"), t("flash_usb"), t("flash_ram")]

    while True:
        # Use select_from_list instead of show_menu for scrolling support
        choice = menu.select_from_list(t("flash_title"), items, show_index=False, show_counter=False)

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
        elif choice == 2:
            result = flash_from_ram(menu)
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

    # Show fetching message
    menu.show_working(t("flash_list"), t("wait"), 0)

    # Get image list
    images = handler.list_available_images()

    if not images:
        result = menu.show_message(t("error"), t("no_images"))
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

    # Confirm download with horizontal choice
    size_mb = image.get('size', 0) // (1024 * 1024) if 'size' in image else image.get('size_mb', 0)
    confirm_msg = f"{t('flash_confirm_download')}\n\n{t('size')}: {size_mb}MB"
    choice = menu.horizontal_choice(confirm_msg, "NO", "YES")
    if choice == -1:
        return -1  # Home
    elif choice != 1:  # Not YES (None or 0)
        return None  # Cancelled

    # Download with progress monitoring
    downloaded_path = [None]  # Use list to allow modification in thread
    download_error = [False]

    def download_thread():
        """Download in background thread"""
        try:
            if 'url' in image:
                result = handler.download_file(image['url'], dest_filename=image['filename'])
            else:
                result = handler.download_file(image['filename'])
            downloaded_path[0] = result
            if not result:
                download_error[0] = True
        except Exception as e:
            download_error[0] = True

    # Start download in background
    thread = threading.Thread(target=download_thread, daemon=True)
    thread.start()

    # Monitor progress while downloading
    temp_path = os.path.join(src_config.TEMP_DIR, image['filename'] + '.partial')
    final_path = os.path.join(src_config.TEMP_DIR, image['filename'])
    expected_size = image.get('size', 0)

    frame = 0
    show_progress_bar = expected_size > 0  # Can we show progress?

    # Show initial state immediately
    if show_progress_bar:
        menu.show_progress(t("flash_downloading"), "", 0)
    else:
        menu.show_working(t("flash_downloading"), "", 0)

    # Monitor very frequently for better progress tracking
    while thread.is_alive():
        # Check if file already exists (complete)
        if os.path.exists(final_path) and not os.path.exists(temp_path):
            # File is already downloaded, just show animation
            menu.show_working(t("flash_downloading"), "", frame % 8)
        # Check if temp file exists and get its size
        elif os.path.exists(temp_path):
            # File is being downloaded, show progress
            try:
                current_size = os.path.getsize(temp_path)
                if show_progress_bar and current_size > 0:
                    percent = min(100, int((current_size / expected_size) * 100))
                    # Always update display for smoother progress
                    menu.show_progress(t("flash_downloading"), "", percent)
                else:
                    # Size unknown or zero, show working animation
                    menu.show_working(t("flash_downloading"), "", frame % 8)
            except OSError:
                # File might be being written, show animation
                menu.show_working(t("flash_downloading"), "", frame % 8)
        else:
            # File not created yet, show animation
            if show_progress_bar:
                # Show 0% if we can track progress
                menu.show_progress(t("flash_downloading"), "", 0)
            else:
                menu.show_working(t("flash_downloading"), "", frame % 8)

        frame += 1
        time.sleep(0.1)  # Update every 0.1 seconds (10 times per second)

    # Wait for thread to complete
    thread.join()

    # Show 100% completion before moving on
    if show_progress_bar and not download_error[0] and downloaded_path[0]:
        menu.show_progress(t("flash_downloading"), "", 100)
        time.sleep(0.5)  # Show 100% for half a second

    # Check result
    if download_error[0] or not downloaded_path[0]:
        result = menu.show_message(t("error"), t("download_failed"))
        if result == -1:
            return -1  # Home
        return None  # Back

    downloaded = downloaded_path[0]

    # Show downloaded message with OK button
    image_name = image.get('name', image.get('filename', 'Image'))
    menu.show_message(t("flash_downloaded"), image_name)

    # Now flash
    result = perform_flash(menu, downloaded)
    if result == -1:
        return -1  # Propagate HOME to main menu


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
    menu.show_working(t("usb_title"), t("usb_detecting"), 0)

    devices = usb_handler.detect_usb_devices()

    if not devices:
        # Show info message (not an error - USB simply not connected)
        result = menu.show_message(t("info"), t("usb_no_device"))
        if result == -1:
            return -1  # Home
        return None  # Back

    # Mount device if needed
    device = devices[0]  # Use first device

    if not device['mountpoint']:
        menu.show_working(t("usb_title"), t("usb_mounting"), 0)
        if not usb_handler.mount_device(device['device']):
            result = menu.show_message(t("error"), t("usb_mount_failed"))
            if result == -1:
                return -1  # Home
            return None  # Back
        mount_point = usb_handler.mount_point
    else:
        mount_point = device['mountpoint']

    # Scan for images
    menu.show_working(t("usb_title"), t("usb_scanning"), 0)
    images = usb_handler.scan_for_images(mount_point)

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


def perform_flash(menu, image_path):
    """
    Perform the actual flash operation

    Args:
        menu: Menu instance
        image_path: Path to image file

    Returns:
        -1 if HOME pressed, None otherwise
    """
    # Confirm flash with horizontal choice
    confirm_msg = f"{t('flash_confirm_flash')}\n\n{t('flash_warning')}"
    choice = menu.horizontal_choice(confirm_msg, "NO", "YES")
    if choice == -1:
        return -1  # Home
    elif choice != 1:  # Not YES (None or 0)
        return None  # Cancelled

    # Flash with default eMMC device
    flash_handler = FlashHandler(emmc_device=src_config.EMMC_DEVICE)

    # Flash in background thread
    flash_result = [False]
    flash_error = [None]

    def flash_thread():
        """Flash in background thread"""
        try:
            # Skip console confirmation - already confirmed on OLED
            result = flash_handler.flash_image(image_path, skip_confirmation=True)
            flash_result[0] = result
        except Exception as e:
            flash_error[0] = str(e)

    # Start flashing in background
    thread = threading.Thread(target=flash_thread, daemon=True)
    thread.start()

    # Show progress animation while flashing
    frame = 0
    while thread.is_alive():
        menu.show_working(t("flash_progress"), "", frame % 8)
        frame += 1
        time.sleep(0.5)

    # Wait for thread to complete
    thread.join()

    # Check result
    if flash_error[0]:
        result = menu.show_message(t("error"), flash_error[0])
        if result == -1:
            return -1  # Home
        return None

    if flash_result[0]:
        result = menu.show_message(t("flash_complete"), t("ok"))
        if result == -1:
            return -1  # Home

        # Ask for reboot with horizontal choice
        reboot_msg = t("reboot_confirm")
        choice = menu.horizontal_choice(reboot_msg, "NO", "YES")
        if choice == -1:
            return -1  # Home
        elif choice == 1:  # YES
            menu.show_message(t("reboot_wait"), "")
            time.sleep(1)
            os.system('reboot')

        return None
    else:
        result = menu.show_message(t("error"), t("flash_failed"))
        if result == -1:
            return -1  # Home
        return None


def flash_from_ram(menu):
    """
    Flash image from Downloaded

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    # Scan for downloaded images in TEMP_DIR
    menu.show_working(t("ram_title"), t("usb_scanning"), 0)

    import glob
    image_files = []
    seen_files = set()

    # Look for image extensions: .img.xz, .xz, .img
    for ext in ['*.img.xz', '*.xz', '*.img']:
        pattern = os.path.join(src_config.TEMP_DIR, ext)
        files = glob.glob(pattern)
        for f in files:
            # Skip .partial files and duplicates
            if not f.endswith('.partial') and f not in seen_files:
                image_files.append(f)
                seen_files.add(f)

    if not image_files:
        result = menu.show_message(t("info"), t("ram_no_images"))
        if result == -1:
            return -1  # Home
        return None  # Back

    # Build list of image names (just filename, not full path)
    image_names = []
    for img_path in image_files:
        filename = os.path.basename(img_path)
        # Get file size
        size_bytes = os.path.getsize(img_path)
        size_mb = size_bytes // (1024 * 1024)
        # Show filename and size
        image_names.append(f"{filename}\n{size_mb}MB")

    # Select image (with counter to show total number of images)
    selected = menu.select_from_list(t("ram_title"), image_names, show_index=True, show_counter=True)

    if selected is None:
        return None  # Cancelled
    elif selected == -1:
        return -1  # Home

    image_path = image_files[selected]
    image_name = os.path.basename(image_path)

    # Show action menu
    while True:
        action_items = [t("ram_flash"), t("ram_delete")]
        # Use select_from_list instead of show_menu for scrolling support and consistency
        action_choice = menu.select_from_list(t("ram_action"), action_items, show_index=False, show_counter=False)

        if action_choice is None:
            return None  # Back to RAM menu
        elif action_choice == -1:
            return -1  # Home
        elif action_choice == 0:
            # Flash
            result = perform_flash(menu, image_path)
            if result == -1:
                return -1  # Propagate HOME to main menu
            return None  # After flash, return to flash menu
        elif action_choice == 1:
            # Delete
            confirm_msg = f"{t('ram_delete')}?\n{image_name[:18]}"
            choice = menu.horizontal_choice(confirm_msg, "NO", "YES")

            if choice == -1:
                return -1  # Home
            elif choice == 1:  # YES
                try:
                    os.remove(image_path)
                    result = menu.show_message(t("ram_deleted"), image_name[:18])
                    if result == -1:
                        return -1  # Home
                    return None  # Back to flash menu
                except Exception as e:
                    result = menu.show_message(t("error"), str(e)[:40])
                    if result == -1:
                        return -1  # Home
                    return None
            # If NO, continue loop to show action menu again

