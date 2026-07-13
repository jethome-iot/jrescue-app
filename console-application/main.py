#!/usr/bin/env python3
"""
Rescue Console Application - Main Entry Point

Curses-only console application for Linux rescue systems to flash eMMC with
images. Supports downloading images via the JetHome API or loading from USB,
with WiFi/Ethernet configuration through NetworkManager.
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
    require_root, clear_screen, print_info, print_error,
    show_menu, show_horizontal_menu, input_dialog,
    show_text_screen, show_wait_screen, show_progress_screen, show_confirm_screen,
    show_settings_screen,
    get_system_info, format_bytes, check_disk_space, ensure_directory,
    check_web_app_status, get_local_ip
)
from network import get_network_handler
from download import download_image_interactive
from usb import list_usb_devices_interactive, USBHandler


def _output_lines(captured: str, limit: int = 40) -> list:
    """Turn captured stdout text into display lines for show_text_screen."""
    lines = [ln.rstrip() for ln in captured.splitlines() if ln.strip()]
    return lines[-limit:]


def network_setup_menu():
    """Network setup submenu"""
    network_handler = get_network_handler()

    if not network_handler:
        show_text_screen("Network", [
            "NetworkManager not available.",
            "nmcli was not found — the recovery image must ship NetworkManager.",
        ])
        return

    while True:
        # Current status goes into the curses menu title — there are no
        # plain-text interstitial screens in the console UI.
        status = network_handler.get_connection_status()
        if status['connected']:
            status_line = status['ip'] or status['interface'] or "connected"
            if status['ssid']:
                status_line = f"{status['ssid']} {status_line}"
        else:
            status_line = "not connected"

        options = [
            t("back_to_main"),
            t("connect_wifi"),
            t("test_connection")
        ]

        choice = show_menu(f'{t("network_options")} · {status_line}', options)

        if choice == 0 or choice == 1:
            # Cancelled or Back
            break

        elif choice == 2:
            # WiFi setup
            wifi_setup(network_handler)

        elif choice == 3:
            # Test connectivity
            _, out = show_wait_screen(
                t("test_connection"), "Testing connection...",
                network_handler.test_connectivity
            )
            show_text_screen(t("test_connection"),
                             _output_lines(out) or ["No output"])


def wifi_setup(network_handler):
    """WiFi configuration (scan, pick, password, connect) — all curses."""
    networks, out = show_wait_screen("WiFi", "Scanning for networks...",
                                     network_handler.scan_wifi)

    if isinstance(networks, Exception) or not networks:
        show_text_screen("WiFi", [
            "No WiFi networks found.",
            "Make sure the WiFi adapter is enabled.",
        ] + _output_lines(out, limit=6))
        return

    # Build menu options
    menu_options = [t("back_cancel")]
    for network in networks:
        security_icon = "🔒" if network['security'] != "Open" else "🔓"
        signal_bars = "█" * (int(network['signal']) // 25)
        menu_line = f"{network['ssid']:<30} {security_icon} [{signal_bars:<4}] {network['signal']}%"
        menu_options.append(menu_line)

    choice = show_menu(f'{t("select_network")} ({len(networks)})', menu_options)

    if choice == 0 or choice == 1:
        return

    network_index = choice - 2
    if not (0 <= network_index < len(networks)):
        return

    selected_network = networks[network_index]
    ssid = selected_network['ssid']

    # Ask for password if secured
    password = None
    if selected_network['security'] != "Open":
        password = input_dialog(
            f"WiFi Password for {ssid}",
            "Enter password",
            password=True
        )
        if password is None:
            return  # cancelled

    result, out = show_wait_screen("WiFi", f"Connecting to {ssid}...",
                                   network_handler.connect_wifi, ssid, password)

    if result is True:
        _, test_out = show_wait_screen(t("test_connection"), "Testing connection...",
                                       network_handler.test_connectivity)
        show_text_screen("WiFi", [f"✓ Connected to {ssid}", ""]
                         + _output_lines(test_out))
    else:
        show_text_screen("WiFi", [f"✗ Failed to connect to {ssid}", ""]
                         + _output_lines(out, limit=10))


def _reboot_prompt():
    """Post-flash success screen: return to menu or reboot."""
    reboot_choice = show_horizontal_menu(
        t("flashing_success"),
        [t("return_menu"), t("reboot_now")]
    )
    if reboot_choice == 2:
        time.sleep(1)
        os.system('reboot')


def flash_to_device(image_path: str, cleanup=None) -> bool:
    """Select target, confirm, flash with a curses progress screen.

    cleanup (optional) runs after flashing regardless of outcome (e.g. USB unmount).
    """
    from flash import FlashHandler, select_target_device

    target_device = select_target_device()
    if not target_device:
        if cleanup:
            cleanup()
        return False

    flash_handler = FlashHandler(emmc_device=target_device)

    if not flash_handler.confirm_flash(image_path):
        if cleanup:
            cleanup()
        return False

    def worker(progress):
        progress(None, os.path.basename(image_path), target_device)
        return flash_handler.flash_image(image_path, skip_confirmation=True,
                                         progress_cb=progress)

    result, out = show_progress_screen("Flashing eMMC", worker)

    if cleanup:
        cleanup()

    if result is True:
        _reboot_prompt()
        return True

    show_text_screen("Flashing failed",
                     _output_lines(out, limit=15) or ["Flashing failed."])
    return False


def flash_from_http():
    """Download image from the JetHome API and flash it"""
    network_handler = get_network_handler()

    if network_handler:
        ok, out = show_wait_screen("Download", "Checking network connection...",
                                   network_handler.test_connectivity)
        if ok is not True:
            show_text_screen("Download", [
                "No internet connection.",
                "Please configure the network first.",
            ] + _output_lines(out, limit=8))
            return False

    # Check RAM space for the compressed image
    free_space = check_disk_space(config.TEMP_DIR)
    if free_space < config.MIN_FREE_SPACE:
        show_text_screen("Download", [
            f"Low RAM space: {format_bytes(free_space)} available.",
            f"Need at least {format_bytes(config.MIN_FREE_SPACE)} for safe operation.",
        ])
        return False

    downloaded_image = download_image_interactive()
    if not downloaded_image:
        return False

    return flash_to_device(downloaded_image)


def flash_from_usb():
    """Load image from USB and flash it"""
    usb_handler = USBHandler()

    device = list_usb_devices_interactive()
    if not device:
        return False

    # Mount device (if not already mounted)
    if device['mountpoint']:
        mount_point = device['mountpoint']
    else:
        ok, out = show_wait_screen("USB", f"Mounting {device['device']}...",
                                   usb_handler.mount_device, device['device'])
        if ok is not True:
            show_text_screen("USB", ["Failed to mount USB device."]
                             + _output_lines(out, limit=8))
            return False
        mount_point = usb_handler.mount_point

    def unmount_if_needed():
        if not device['mountpoint']:
            usb_handler.unmount_device()

    # Scan for images
    images, out = show_wait_screen("USB", "Scanning for images...",
                                   usb_handler.scan_for_images, mount_point)
    if isinstance(images, Exception) or not images:
        unmount_if_needed()
        show_text_screen("USB", ["No image files found on USB."]
                         + _output_lines(out, limit=8))
        return False

    # Build menu options
    menu_options = [t("back_cancel")]
    for image in images:
        menu_line = f"{image['filename']} | {format_bytes(image['size'])} | {image['relative_path']}"
        menu_options.append(menu_line)

    choice = show_menu(f'{t("select_image_usb")} ({len(images)})', menu_options)

    if choice == 0 or choice == 1:
        unmount_if_needed()
        return False

    image_index = choice - 2
    if not (0 <= image_index < len(images)):
        unmount_if_needed()
        return False

    selected_image = images[image_index]
    return flash_to_device(selected_image['path'], cleanup=unmount_if_needed)


def manage_ram_images():
    """Manage downloaded images in RAM - flash or delete"""
    while True:
        ram_dir = config.TEMP_DIR
        if not os.path.exists(ram_dir):
            show_text_screen(t("images_in_ram"),
                             [f"RAM directory not found: {ram_dir}"])
            return False

        image_files = []
        for filename in os.listdir(ram_dir):
            if filename.endswith(('.img', '.img.xz', '.xz')):
                filepath = os.path.join(ram_dir, filename)
                if os.path.isfile(filepath):
                    image_files.append({
                        'filename': filename,
                        'path': filepath,
                        'size': os.path.getsize(filepath)
                    })

        if not image_files:
            show_text_screen(t("images_in_ram"), [
                f"No images found in RAM ({ram_dir}).",
                "Download an image first using the API download option.",
            ])
            return False

        menu_options = ["← Back to Flash Menu"]
        for img in image_files:
            menu_options.append(f"{img['filename']} ({format_bytes(img['size'])})")

        choice = show_menu(t("images_in_ram"), menu_options)

        if choice == 0 or choice == 1:
            return False

        image_index = choice - 2
        if not (0 <= image_index < len(image_files)):
            continue

        selected = image_files[image_index]

        action_options = [
            t("back_to_image_list"),
            t("action_flash"),
            t("action_delete")
        ]

        action_choice = show_menu(
            f"{selected['filename']} ({format_bytes(selected['size'])})",
            action_options
        )

        if action_choice == 0 or action_choice == 1:
            continue  # Back to image list

        elif action_choice == 2:
            # Flash image
            if flash_to_device(selected['path']):
                return True

        elif action_choice == 3:
            # Delete image
            confirmed = show_confirm_screen(
                t("confirm_deletion"),
                [
                    selected['filename'],
                    f"{t('size')}: {format_bytes(selected['size'])}",
                    "",
                    "Deleting frees RAM for new downloads.",
                ],
                yes_label=t("yes_delete"),
                no_label=t("cancel"),
            )
            if confirmed:
                try:
                    os.remove(selected['path'])
                except Exception as e:
                    show_text_screen(t("confirm_deletion"),
                                     [f"Failed to delete: {e}"])
                # Loop back to the (updated) image list


def flash_image_menu():
    """Flash image to eMMC - with source selection"""
    while True:
        options = [
            t("back_to_main"),
            t("source_http"),
            t("source_usb"),
            "Flash from Downloaded"
        ]

        source_choice = show_menu(t("select_image_source"), options)

        if source_choice == 0 or source_choice == 1:
            return

        elif source_choice == 2:
            if flash_from_http():
                return

        elif source_choice == 3:
            if flash_from_usb():
                return

        elif source_choice == 4:
            if manage_ram_images():
                return


def system_info_menu():
    """Display system information in a scrollable curses screen."""
    def collect():
        info = get_system_info()

        lines = [
            f"Hostname:      {info['hostname']}",
            f"Kernel:        {info['kernel']}",
            f"Architecture:  {info['arch']}",
            f"Memory:        {info['memory']}",
            f"Free Space:    {info['disk_free']}",
            "",
            f"Device:        {config.JETHOME_DEVICE_NAME}",
            f"Platform:      {config.JETHOME_PLATFORM}",
            f"Version:       {config.APP_VERSION}",
            "",
            f"eMMC Device:   {config.EMMC_DEVICE}",
            f"Temp Dir:      {config.TEMP_DIR}",
            f"USB Mount:     {config.USB_MOUNT_POINT}",
            "",
        ]

        network_handler = get_network_handler()
        if network_handler:
            status = network_handler.get_connection_status()
            if status['connected']:
                lines.append(f"Network:       Connected ({status['interface']})")
                if status['ip']:
                    lines.append(f"IP Address:    {status['ip']}")
                if status['ssid']:
                    lines.append(f"WiFi:          {status['ssid']}")
            else:
                lines.append("Network:       Not connected")

        lines.append("")

        web_port = 8124
        if check_web_app_status("localhost", web_port):
            local_ip = get_local_ip() or "localhost"
            lines.append("Web UI:        Running")
            lines.append(f"Access URL:    http://{local_ip}:{web_port}")
        else:
            lines.append(f"Web UI:        Not running (port {web_port})")
        return lines

    lines, _ = show_wait_screen(t("system_info"), "Collecting system info...", collect)
    if isinstance(lines, Exception):
        lines = [f"Failed to collect system info: {lines}"]
    show_text_screen("SYSTEM INFORMATION", lines)


def settings_menu():
    """menuconfig-style runtime settings (reset on reboot)."""
    items = [
        {
            'type': 'choice',
            'label': 'Language',
            'choices': [('en', 'English'), ('ru', 'Русский')],
            'get': app_locale.get_language,
            'set': app_locale.set_language,
            'help': "Interface language for the console application.\n"
                    "Applies immediately to all menus.",
        },
        {
            'type': 'int',
            'label': 'Network timeout (s)',
            'get': lambda: config.NETWORK_TIMEOUT,
            'set': lambda v: setattr(config, 'NETWORK_TIMEOUT', v),
            'help': "Timeout for API requests and downloads, in seconds.",
        },
        {
            'type': 'bool',
            'label': 'Verbose logs',
            'get': lambda: config.VERBOSE_LOGS,
            'set': lambda v: setattr(config, 'VERBOSE_LOGS', v),
            'help': "Show informational messages in captured\n"
                    "operation output (connection test, flashing).",
        },
    ]
    show_settings_screen(t("settings"), items)


def drop_to_shell():
    """Exit curses and run a root shell on this tty; the app resumes on exit."""
    clear_screen()
    print("═" * 60)
    print(" jrescue shell — type 'exit' to return to the menu")
    print("═" * 60)
    try:
        import subprocess
        # --norc/--noprofile so nothing overrides our visible prompt
        env = dict(os.environ)
        env['PS1'] = r'jrescue \w # '
        subprocess.call(['/bin/bash', '--norc', '--noprofile', '-i'], env=env)
    except Exception as e:
        print_error(f"Shell failed: {e}")


def main_menu():
    """Main menu loop"""
    while True:
        # Web UI address lives in the menu title so it is always visible
        # without a plain-text interstitial print.
        web_port = 8124
        title = t("main_menu")
        if check_web_app_status("localhost", web_port):
            local_ip = get_local_ip() or "localhost"
            title = f"{title} · http://{local_ip}:{web_port}"

        options = [
            t("network_setup"),
            t("flash_image"),
            t("system_info"),
            t("settings"),
            t("shell")
        ]

        choice = show_menu(title, options)

        if choice == 0:
            continue

        elif choice == 1:
            network_setup_menu()

        elif choice == 2:
            flash_image_menu()

        elif choice == 3:
            system_info_menu()

        elif choice == 4:
            settings_menu()

        elif choice == 5:
            drop_to_shell()


def cleanup_old_temp_dir():
    """Clean up old temporary directory if it exists"""
    old_temp_dir = "/var/rescue"
    if os.path.exists(old_temp_dir) and old_temp_dir != config.TEMP_DIR:
        try:
            for item in os.listdir(old_temp_dir):
                item_path = os.path.join(old_temp_dir, item)
                # Only remove image files, keep logs
                if item.endswith(('.img', '.img.xz', '.xz')) and not item.endswith('.log'):
                    try:
                        os.remove(item_path)
                    except Exception as e:
                        print_error(f"Failed to remove {item}: {e}")
        except Exception as e:
            print_error(f"Failed to clean old temp directory: {e}")


def main():
    """Main entry point"""
    try:
        # Check root privileges
        require_root()

        # Language selection (curses)
        clear_screen()
        lang_code = app_locale.select_language_interactive()
        app_locale.set_language(lang_code)

        # Ensure directories exist
        ensure_directory(config.TEMP_DIR)
        ensure_directory(config.USB_MOUNT_POINT)

        # Clean up old temporary directory (migration from v1.2.1)
        cleanup_old_temp_dir()

        # Straight into the curses main menu — no plain-text banner
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
