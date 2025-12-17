#!/usr/bin/env python3
"""
Rescue Console Application - Main Entry Point

Interactive console application for Linux rescue systems to flash eMMC with images.
Supports downloading images via HTTP or loading from USB, with WiFi/Ethernet configuration.
"""

import sys
import os
import time

# Add core directory to path
_core_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core')
sys.path.insert(0, _core_path)

# Import from core
import config
import translations as app_locale
from translations import t
from utils import (
    require_root, clear_screen, print_header, print_info, print_success,
    print_error, print_warning, show_menu, show_horizontal_menu, input_dialog, press_enter_to_continue, get_system_info,
    format_bytes, check_disk_space, ensure_directory, print_info, find_mmcblk_devices,
    check_web_app_status, get_local_ip, create_clickable_link
)
from network import get_network_handler
from download import download_image_interactive, DownloadHandler
from usb import list_usb_devices_interactive, USBHandler
from flash import flash_image_interactive


def show_banner():
    """Display application banner"""
    title = t("app_title")
    subtitle = t("app_subtitle")
    device_line = f"{t('device')}: {config.JETHOME_DEVICE_NAME}"

    banner = f"""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║                    {title:<55}║
║                           Version {config.APP_VERSION}                            ║
║                                                                       ║
║              {subtitle:<55}║
║                     {device_line:<46}║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def network_setup_menu():
    """Network setup submenu"""
    network_handler = get_network_handler()

    if not network_handler:
        print_error("wpa_supplicant not available")
        print_warning("Please install: apt install wpa_supplicant")
        press_enter_to_continue()
        return

    while True:
        clear_screen()
        print_header("NETWORK SETUP")

        # Show current status
        status = network_handler.get_connection_status()
        if status['connected']:
            print_success(f"Connected: {status['interface']}")
            if status['ip']:
                print_info(f"IP Address: {status['ip']}")
            if status['ssid']:
                print_info(f"WiFi Network: {status['ssid']}")
        else:
            print_info("Status: Not connected")

        print()

        options = [
            t("back_to_main"),
            t("connect_wifi"),
            t("test_connection")
        ]

        choice = show_menu(t("network_options"), options)

        if choice == 0 or choice == 1:
            # Cancelled or Back
            break

        elif choice == 2:
            # WiFi setup
            wifi_setup(network_handler)

        elif choice == 3:
            # Test connectivity
            print()
            network_handler.test_connectivity()
            press_enter_to_continue()


def wifi_setup(network_handler):
    """WiFi configuration"""
    clear_screen()
    print_header("WiFi SETUP")

    # Scan for networks
    networks = network_handler.scan_wifi()

    if not networks:
        print_error("No WiFi networks found")
        print_info("Make sure WiFi adapter is enabled")
        press_enter_to_continue()
        return

    print()
    print_success(f"Found {len(networks)} network(s)")
    print_info("Use ↑↓ arrow keys to navigate, Enter to select")
    print()

    # Build menu options
    menu_options = []
    menu_options.append(t("back_cancel"))

    for network in networks:
        security_icon = "🔒" if network['security'] != "Open" else "🔓"
        signal_bars = "█" * (int(network['signal']) // 25)
        menu_line = f"{network['ssid']:<30} {security_icon} [{signal_bars:<4}] {network['signal']}%"
        menu_options.append(menu_line)

    choice = show_menu(t("select_network"), menu_options)

    # choice == 0 or 1 means cancelled
    if choice == 0 or choice == 1:
        return

    # choice >= 2 means a network was selected
    network_index = choice - 2
    if 0 <= network_index < len(networks):
        selected_network = networks[network_index]
        ssid = selected_network['ssid']

        print()
        print_info(f"Selected: {ssid}")

        # Ask for password if secured
        password = None
        if selected_network['security'] != "Open":
            # Use interactive dialog for password input
            password = input_dialog(
                f"WiFi Password for {ssid}",
                "Enter password",
                password=True
            )

            if password is None:
                # User cancelled
                print_info("WiFi setup cancelled")
                press_enter_to_continue()
                return

                if not password:
                    print_error("Password cannot be empty")
                    press_enter_to_continue()
                return

        print()

        # Connect
        if network_handler.connect_wifi(ssid, password):
            print()
            print_success("WiFi connection established!")

            # Test connectivity
            print()
            network_handler.test_connectivity()
        else:
            print()
            print_error("Failed to connect to WiFi")

        press_enter_to_continue()


def ethernet_setup(network_handler):
    """Ethernet configuration"""
    clear_screen()
    print_header("ETHERNET SETUP")

    print_info("Configuring Ethernet with DHCP...")
    print()

    if network_handler.connect_ethernet():
        print()
        print_success("Ethernet connection established!")

        # Test connectivity
        print()
        network_handler.test_connectivity()
    else:
        print()
        print_error("Failed to configure Ethernet")
        print_info("Check cable connection and network settings")

    press_enter_to_continue()


def download_image_menu():
    """Download image via HTTP"""
    clear_screen()
    print_header("DOWNLOAD IMAGE VIA HTTP")

    # Check network connectivity
    print_info("Checking network connection...")
    network_handler = get_network_handler()

    if network_handler and not network_handler.test_connectivity():
        print()
        print_error("No internet connection")
        print_info("Please configure network first")
        press_enter_to_continue()
        return

    print()

    # Check disk space (only warn if insufficient)
    free_space = check_disk_space(config.TEMP_DIR)

    if free_space < config.MIN_FREE_SPACE:
        print_warning(f"Low disk space: {format_bytes(free_space)} available")
        print_error(f"Need at least {format_bytes(config.MIN_FREE_SPACE)} for safe operation")
        press_enter_to_continue()
        return

    print()

    # Download
    result = download_image_interactive()

    print()
    if result:
        print_success(f"Image downloaded successfully!")
        print_info(f"Location: {result}")
    else:
        print_info("Download cancelled or failed")

    press_enter_to_continue()


def load_image_from_usb_menu():
    """Load image from USB"""
    clear_screen()
    print_header("LOAD IMAGE FROM USB")

    usb_handler = USBHandler()

    # Detect USB devices
    device = list_usb_devices_interactive()

    if not device:
        print_info("No USB device selected")
        press_enter_to_continue()
        return

    print()

    # Mount device
    if device['mountpoint']:
        print_info(f"Device already mounted at {device['mountpoint']}")
        mount_point = device['mountpoint']
    else:
        if not usb_handler.mount_device(device['device']):
            print_error("Failed to mount USB device")
            press_enter_to_continue()
            return
        mount_point = usb_handler.mount_point

    print()

    # Scan for images
    images = usb_handler.scan_for_images(mount_point)

    if not images:
        print_error("No image files found on USB")

        # Unmount if we mounted it
        if not device['mountpoint']:
            usb_handler.unmount_device()

        press_enter_to_continue()
        return

    print()
    print_info(f"Found {len(images)} image file(s) on USB")
    print_info("Use ↑↓ arrow keys to navigate, Enter to select")
    print()

    # Build menu options
    menu_options = []
    menu_options.append(t("back_cancel"))

    for image in images:
        menu_line = f"{image['filename']} | {format_bytes(image['size'])} | {image['relative_path']}"
        menu_options.append(menu_line)

    choice = show_menu(t("select_image_usb"), menu_options)

    # choice == 0 or 1 means cancelled or "Back" selected
    if choice == 0 or choice == 1:
        # Unmount if we mounted it
        if not device['mountpoint']:
            usb_handler.unmount_device()
        press_enter_to_continue()
        return

    # choice >= 2 means an image was selected
    image_index = choice - 2
    if 0 <= image_index < len(images):
        selected_image = images[image_index]

        print()
        print_success(f"Selected: {selected_image['filename']}")
        print_info(f"Path: {selected_image['path']}")
        print_info(f"Size: {format_bytes(selected_image['size'])}")
        print_warning("DO NOT REMOVE USB drive until flashing is complete!")
        print()

        image_to_flash = selected_image['path']

        # Select target device
        from flash import FlashHandler, select_target_device

        print_info("Select target device for flashing:")
        print()

        target_device = select_target_device()
        if not target_device:
            print_info("No device selected")
            # Unmount if we mounted it
            if not device['mountpoint']:
                usb_handler.unmount_device()
            press_enter_to_continue()
            return

        print()
        print_success(f"Target device: {target_device}")

        # Flash image (from USB or local copy)
        print()
        flash_handler = FlashHandler(emmc_device=target_device)

        success = flash_handler.flash_image(image_to_flash)

        # Unmount if we mounted it
        if not device['mountpoint']:
            print()
            usb_handler.unmount_device()

        if success:
            print()
            print_info("You can now safely remove USB drive")
            print()

            # Ask for reboot using interactive horizontal menu
            reboot_choice = show_horizontal_menu(
                t("flashing_success"),
                [t("return_menu"), t("reboot_now")]
            )

            if reboot_choice == 2:
                print_info("Rebooting...")
                time.sleep(1)
                os.system('reboot')
                return  # Don't call press_enter_to_continue
        else:
            print()
            print_error("Flashing failed")
    else:
        # Unmount if we mounted it
        if not device['mountpoint']:
            usb_handler.unmount_device()

    press_enter_to_continue()


def flash_from_http():
    """Download image from HTTP and flash it"""
    clear_screen()
    print_header("DOWNLOAD & FLASH FROM HTTP")

    # Check network connectivity
    print_info("Checking network connection...")
    network_handler = get_network_handler()

    if network_handler and not network_handler.test_connectivity():
        print()
        print_error("No internet connection")
        print_info("Please configure network first")
        press_enter_to_continue()
        return False

    print()

    # Check disk space
    free_space = check_disk_space(config.TEMP_DIR)

    if free_space < config.MIN_FREE_SPACE:
        print_warning(f"Low RAM space: {format_bytes(free_space)} available")
        print_error(f"Need at least {format_bytes(config.MIN_FREE_SPACE)} for safe operation")
        press_enter_to_continue()
        return False

    print()

    # Download image
    downloaded_image = download_image_interactive()

    if not downloaded_image:
        print()
        print_info("Download cancelled or failed")
        press_enter_to_continue()
        return False

    print()
    print_success(f"Image downloaded: {downloaded_image}")
    print()

    # Select target device
    from flash import FlashHandler, select_target_device

    print_info("Select target device for flashing:")
    print()

    target_device = select_target_device()
    if not target_device:
        print_info("No device selected")
        press_enter_to_continue()
        return False

    print()
    print_success(f"Target device: {target_device}")
    print()

    # Flash the image
    flash_handler = FlashHandler(emmc_device=target_device)
    success = flash_handler.flash_image(downloaded_image)

    if success:
        print()
        # Ask for reboot
        reboot_choice = show_horizontal_menu(
            t("flashing_success"),
            [t("return_menu"), t("reboot_now")]
        )

        if reboot_choice == 2:
            print_info("Rebooting...")
            time.sleep(1)
            os.system('reboot')

        return True
    else:
        print()
        print_error("Flashing failed")
        press_enter_to_continue()
        return False


def flash_from_usb():
    """Load image from USB and flash it"""
    clear_screen()
    print_header("LOAD & FLASH FROM USB")

    usb_handler = USBHandler()

    # Detect USB devices
    device = list_usb_devices_interactive()

    if not device:
        print_info("No USB device selected")
        press_enter_to_continue()
        return False

    print()

    # Mount device
    if device['mountpoint']:
        print_info(f"Device already mounted at {device['mountpoint']}")
        mount_point = device['mountpoint']
    else:
        if not usb_handler.mount_device(device['device']):
            print_error("Failed to mount USB device")
            press_enter_to_continue()
            return False
        mount_point = usb_handler.mount_point

    print()

    # Scan for images
    images = usb_handler.scan_for_images(mount_point)

    if not images:
        print_error("No image files found on USB")
        # Unmount if we mounted it
        if not device['mountpoint']:
            usb_handler.unmount_device()
        press_enter_to_continue()
        return False

    print()
    print_info(f"Found {len(images)} image file(s) on USB")
    print_info("Use ↑↓ arrow keys to navigate, Enter to select")
    print()

    # Build menu options
    menu_options = []
    menu_options.append(t("back_cancel"))

    for image in images:
        menu_line = f"{image['filename']} | {format_bytes(image['size'])} | {image['relative_path']}"
        menu_options.append(menu_line)

    choice = show_menu(t("select_image_usb"), menu_options)

    # choice == 0 or 1 means cancelled
    if choice == 0 or choice == 1:
        if not device['mountpoint']:
            usb_handler.unmount_device()
        return False

    # choice >= 2 means an image was selected
    image_index = choice - 2
    if 0 <= image_index < len(images):
        selected_image = images[image_index]

        print()
        print_success(f"Selected: {selected_image['filename']}")
        print_info(f"Path: {selected_image['path']}")
        print_info(f"Size: {format_bytes(selected_image['size'])}")
        print_warning("DO NOT REMOVE USB drive until flashing is complete!")
        print()

        image_to_flash = selected_image['path']

        # Select target device
        from flash import FlashHandler, select_target_device

        print_info("Select target device for flashing:")
        print()

        target_device = select_target_device()
        if not target_device:
            print_info("No device selected")
            if not device['mountpoint']:
                usb_handler.unmount_device()
            press_enter_to_continue()
            return False

        print()
        print_success(f"Target device: {target_device}")
        print()

        # Flash image
        flash_handler = FlashHandler(emmc_device=target_device)
        success = flash_handler.flash_image(image_to_flash)

        # Unmount if we mounted it
        if not device['mountpoint']:
            print()
            usb_handler.unmount_device()

        if success:
            print()
            print_info("You can now safely remove USB drive")
            print()

            # Ask for reboot
            reboot_choice = show_horizontal_menu(
                t("flashing_success"),
                [t("return_menu"), t("reboot_now")]
            )

            if reboot_choice == 2:
                print_info("Rebooting...")
                time.sleep(1)
                os.system('reboot')

            return True
        else:
            print()
            print_error("Flashing failed")
            press_enter_to_continue()
            return False
    else:
        if not device['mountpoint']:
            usb_handler.unmount_device()
        return False


def manage_ram_images():
    """Manage images in RAM - view, flash, or delete"""

    while True:
        clear_screen()
        print_header(t("flash_downloaded"))

        # List images in RAM
        ram_dir = config.TEMP_DIR
        if not os.path.exists(ram_dir):
            print_error(f"RAM directory not found: {ram_dir}")
            press_enter_to_continue()
            return False

        # Find image files
        image_files = []
        for filename in os.listdir(ram_dir):
            # Check for image file extensions
            if filename.endswith(('.img', '.img.xz', '.xz')):
                filepath = os.path.join(ram_dir, filename)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    image_files.append({
                        'filename': filename,
                        'path': filepath,
                        'size': size
                    })

        if not image_files:
            print_info(f"No images found in RAM ({ram_dir})")
            print_info("Download an image first using 'Download from HTTP' option")
            press_enter_to_continue()
            return False

        print_success(f"Found {len(image_files)} image(s) in RAM:")
        print()

        # Build menu options
        menu_options = ["← Back to Flash Menu"]
        for idx, img in enumerate(image_files, 1):
            menu_options.append(f"{img['filename']} ({format_bytes(img['size'])})")

        print_info("Select an image to manage:")
        print()

        choice = show_menu(t("images_in_ram"), menu_options)

        if choice == 0 or choice == 1:
            return False

        # Image selected
        image_index = choice - 2
        if 0 <= image_index < len(image_files):
            selected = image_files[image_index]

            # Show action menu
            clear_screen()
            print_header(f"MANAGE: {selected['filename']}")
            print()
            print_info(f"File: {selected['filename']}")
            print_info(f"Size: {format_bytes(selected['size'])}")
            print_info(f"Path: {selected['path']}")
            print()

            action_options = [
                t("back_to_image_list"),
                t("action_flash"),
                t("action_delete")
            ]

            action_choice = show_menu(t("select_action"), action_options)

            if action_choice == 0 or action_choice == 1:
                continue  # Back to image list

            elif action_choice == 2:
                # Flash image
                print()

                # Select target device
                from flash import FlashHandler, select_target_device

                print_info("Select target device for flashing:")
                print()

                target_device = select_target_device()
                if not target_device:
                    print_info("No device selected")
                    press_enter_to_continue()
                    continue

                print()
                print_success(f"Target device: {target_device}")
                print()

                # Flash the image
                flash_handler = FlashHandler(emmc_device=target_device)
                success = flash_handler.flash_image(selected['path'])

                if success:
                    print()
                    # Ask for reboot
                    reboot_choice = show_horizontal_menu(
                        t("flashing_success"),
                        [t("return_menu"), t("reboot_now")]
                    )

                    if reboot_choice == 2:
                        print_info("Rebooting...")
                        time.sleep(1)
                        os.system('reboot')

                    return True
                else:
                    print()
                    print_error("Flashing failed")
                    press_enter_to_continue()

            elif action_choice == 3:
                # Delete image
                print()
                print_warning(f"Delete {selected['filename']}?")
                print_info(f"This will free {format_bytes(selected['size'])} of RAM")
                print()

                confirm_choice = show_horizontal_menu(
                    t("confirm_deletion"),
                    [t("cancel"), t("yes_delete")]
                )

                if confirm_choice == 2:
                    try:
                        os.remove(selected['path'])
                        print()
                        print_success(f"Deleted: {selected['filename']}")
                        print_info(f"Freed {format_bytes(selected['size'])} of RAM")
                    except Exception as e:
                        print()
                        print_error(f"Failed to delete: {e}")

                    press_enter_to_continue()
                    # Return to image list to show updated list
                    continue


def flash_from_temp():
    """Select already downloaded image and flash it - DEPRECATED, use manage_ram_images"""
    return manage_ram_images()


def flash_image_menu():
    """Flash image to eMMC - with source selection"""
    while True:
        clear_screen()
        print_header(t("flash_menu"))

        print_info(t("select_source"))
        print()

        options = [
            t("back_to_main"),
            t("source_http"),
            t("source_usb"),
            "Flash from Downloaded"
        ]

        source_choice = show_menu(t("select_image_source"), options)

        if source_choice == 0 or source_choice == 1:
            # Back to main menu
            return

        elif source_choice == 2:
            # Download from HTTP
            result = flash_from_http()
            if result:
                return  # Return to main menu after successful flash

        elif source_choice == 3:
            # Load from USB
            result = flash_from_usb()
            if result:
                return  # Return to main menu after successful flash

        elif source_choice == 4:
            # Flash from Downloaded
            result = manage_ram_images()
            if result:
                return  # Return to main menu after successful flash




def system_info_menu():
    """Display system information"""
    clear_screen()
    print_header("SYSTEM INFORMATION")

    info = get_system_info()

    print(f"  Hostname:      {info['hostname']}")
    print(f"  Kernel:        {info['kernel']}")
    print(f"  Architecture:  {info['arch']}")
    print(f"  Memory:        {info['memory']}")
    print(f"  Free Space:    {info['disk_free']}")
    print()

    # Current device
    print(f"  Device:        {config.JETHOME_DEVICE_NAME}")
    print(f"  Platform:      {config.JETHOME_PLATFORM}")
    print()

    print(f"  eMMC Device:   {config.EMMC_DEVICE}")
    print(f"  Temp Dir:      {config.TEMP_DIR}")
    print(f"  USB Mount:     {config.USB_MOUNT_POINT}")
    print(f"  Server URL:    {config.DEFAULT_SERVER}")
    print()

    # Network status
    network_handler = get_network_handler()
    if network_handler:
        status = network_handler.get_connection_status()
        if status['connected']:
            print_success(f"Network: Connected ({status['interface']})")
            if status['ip']:
                print(f"  IP Address:    {status['ip']}")
            if status['ssid']:
                print(f"  WiFi:          {status['ssid']}")
        else:
            print_info("Network: Not connected")

    print()

    # Web application status
    web_port = 8124
    web_running = check_web_app_status("localhost", web_port)

    if web_running:
        print_success(f"Web Application: Running on port {web_port}")

        # Get local IP for access
        local_ip = get_local_ip()
        if local_ip:
            web_url = f"http://{local_ip}:{web_port}"
            print(f"  Access URL:    {create_clickable_link(web_url, web_url)}")
        else:
            web_url = f"http://localhost:{web_port}"
            print(f"  Access URL:    {create_clickable_link(web_url, web_url)}")
    else:
        print_warning(f"Web Application: Not running (port {web_port})")

    press_enter_to_continue()


def main_menu():
    """Main menu loop"""
    while True:
        # Show web app status before menu (always visible)
        web_port = 8124
        web_running = check_web_app_status("localhost", web_port)
        if web_running:
            local_ip = get_local_ip()
            if local_ip:
                web_url = f"http://{local_ip}:{web_port}"
            else:
                web_url = f"http://localhost:{web_port}"
            print_info(f"Web Interface: {create_clickable_link(web_url, web_url)}")
            print()

        options = [
            t("network_setup"),
            t("flash_image"),
            t("system_info")
        ]

        choice = show_menu(t("main_menu"), options)

        if choice == 0:
            # Cancelled (only in classic menu)
            continue

        elif choice == 1:
            network_setup_menu()

        elif choice == 2:
            flash_image_menu()

        elif choice == 3:
            system_info_menu()


def cleanup_old_temp_dir():
    """Clean up old temporary directory if it exists"""
    old_temp_dir = "/var/rescue"
    if os.path.exists(old_temp_dir) and old_temp_dir != config.TEMP_DIR:
        try:
            import shutil
            # Remove old downloaded images
            for item in os.listdir(old_temp_dir):
                item_path = os.path.join(old_temp_dir, item)
                # Only remove image files, keep logs
                if item.endswith(('.img', '.img.xz', '.xz')) and not item.endswith('.log'):
                    try:
                        os.remove(item_path)
                        print_info(f"Cleaned up old image: {item}")
                    except Exception as e:
                        print_error(f"Failed to remove {item}: {e}")
        except Exception as e:
            print_error(f"Failed to clean old temp directory: {e}")


def main():
    """Main entry point"""
    try:
        # Check root privileges
        require_root()

        # Language selection
        clear_screen()
        lang_code = app_locale.select_language_interactive()
        app_locale.set_language(lang_code)

        # Show banner with selected language
        clear_screen()
        show_banner()

        # Ensure directories exist
        ensure_directory(config.TEMP_DIR)
        ensure_directory(config.USB_MOUNT_POINT)

        # Clean up old temporary directory (migration from v1.2.1)
        cleanup_old_temp_dir()

        # Log startup
        print_info(app_locale.t("info") + ": Rescue Console Application started")

        # Run main menu
        main_menu()

    except KeyboardInterrupt:
        print("\n")
        print_info("Application interrupted by user")
        sys.exit(0)

    except Exception as e:
        print_error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

