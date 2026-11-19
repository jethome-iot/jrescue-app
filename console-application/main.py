#!/usr/bin/env python3
"""Classic recovery console sharing network, download and protected image writers."""

import os
import signal
import sys

_core_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core')
sys.path.insert(0, _core_path)

import config
import ap
import translations as app_locale
import tui
from translations import t
from utils import (require_root, print_info, print_error, run_command, show_menu,
                   show_horizontal_menu, input_dialog, show_text_screen,
                   show_wait_screen, show_progress_screen, show_confirm_screen,
                   show_compact_confirmation,
                   show_table_menu, show_network_screen, show_power_pending,
                   run_console_ui, format_bytes, check_disk_space, ensure_directory)
from network import get_network_handler, get_web_urls, get_web_endpoints
from network_control import restart_network
from system_info import get_recovery_info, get_memory_info
from download import DownloadHandler, download_image_interactive
from usb import list_usb_devices_interactive, USBHandler


def _output_lines(captured, limit=40):
    """Keep diagnostic output bounded and inside curses."""
    return [line.rstrip() for line in captured.splitlines() if line.strip()][-limit:]


def wifi_error_lines(code, ssid=None):
    """Put the cause and next step before any potentially long SSID."""
    known = {'wrong_password', 'bad_password_format', 'auth_failed', 'not_found', 'no_dhcp',
           'timeout', 'radio_busy', 'no_wifi', 'unavailable', 'busy'}
    code = code if code in known else 'unknown'
    hint = ('password' if code in ('wrong_password', 'bad_password_format', 'auth_failed') else
          'router' if code == 'no_dhcp' else 'scan' if code == 'not_found' else
          'adapter' if code in ('radio_busy', 'no_wifi') else 'retry')
    lines = [t('tui_wifi_reason_' + code), t('tui_wifi_hint_' + hint)]
    if ssid is not None:
        lines += ['', 'SSID: ' + ssid]
    return lines


def network_setup_menu():
    """Switch Network tab contents directly, loading read-only data on demand."""
    handler, output = show_wait_screen(t('tui_network'), t('tui_wait'), get_network_handler)
    if isinstance(handler, Exception) or not handler:
        show_text_screen(t('tui_network'), [t('nm_unavailable'), t('nm_unavailable_hint')])
        return
    tab, devices, scan, wifi_index = 'status', None, None, 0
    restart_return = 'status'
    while True:
        if devices is None:
            devices, output = show_wait_screen(t('tui_network'), t('tui_network_refresh'), handler.get_network_status)
            if isinstance(devices, Exception) or (not devices and getattr(handler, 'last_error', '')):
                show_text_screen(t('tui_network'), [t('tui_network_failed')])
                return
        if tab == 'wifi' and scan is None:
            scan, output = show_wait_screen(t('tui_wifi'), t('scanning_networks'), wifi_networks, handler)
            if isinstance(scan, Exception):
                scan = {'networks': [], 'errors': wifi_error_lines('unknown')}
        request = show_network_screen(devices or [], tab=tab,
                                      networks=(scan or {}).get('networks', []),
                                      error_lines=(scan or {}).get('errors'),
                                      notice=(scan or {}).get('notice'), wifi_index=wifi_index,
                                      return_tab=restart_return)
        if request is None:
            return
        if request['tab'] == 'restart' and tab != 'restart':
            restart_return = tab
        tab, wifi_index = request['tab'], request['wifi_index']
        if request['action'] == 'refresh':
            if tab == 'wifi':
                scan = None
            else:
                devices = None
        elif request['action'] == 'connect':
            networks = (scan or {}).get('networks', [])
            if 0 <= wifi_index < len(networks):
                def background(rows, cols):
                    return tui.network_frame(rows, cols, devices or [], selected=1,
                        networks=networks, wifi_index=wifi_index,
                        notice=(scan or {}).get('notice'))[0]
                wifi_setup(handler, selected=networks[wifi_index], background=background)
                devices, scan = None, None
        elif request['action'] == 'restart':
            # The modal returns this only after an explicit OK.
            restart_network_menu(confirmed=True)
            devices, scan = None, None
            tab = 'status'


def restart_network_menu(confirmed=False):
    """Restart existing connections after the compact OK/Cancel dialog."""
    if not confirmed and not show_compact_confirmation(t('tui_restart_confirm'),
                                    [t('tui_restart_warning'), '', t('tui_restart_profiles')]):
        return
    result, output = show_wait_screen(t('tui_restart'), t('tui_restarting'), restart_network, 'manager')
    if not isinstance(result, dict) or not result.get('ok'):
        code = result.get('error') if isinstance(result, dict) else 'failed'
        show_text_screen(t('tui_restart'), [t('tui_network_busy' if code == 'busy' else 'tui_network_failed')])


def wifi_networks(network_handler):
    """Viewing a tab must not disconnect the setup AP to perform a fresh scan."""
    ap_handler = ap.get_ap_handler()
    if ap_handler.is_ap_active():
        networks = ap_handler.read_scan_cache()
        return {'networks': networks, 'notice': t('tui_wifi_cached'),
                'errors': None if networks else [t('tui_wifi_cached'), t('tui_wifi_cached_empty')]}
    networks = network_handler.scan_wifi()
    if not networks:
        code = getattr(network_handler, 'last_error_code', '')
        return {'networks': [], 'errors': wifi_error_lines(code) if code else [t('no_networks'), t('make_sure_wifi')]}
    return {'networks': networks}


def wifi_setup(network_handler, selected=None, background=None):
    """Edit credentials first, then release the AP only for an explicit connection."""
    if selected is None:
        scan, output = show_wait_screen(t('tui_wifi'), t('scanning_networks'), wifi_networks, network_handler)
        if isinstance(scan, Exception) or not scan.get('networks'):
            show_text_screen(t('tui_wifi'), wifi_error_lines('unknown') if isinstance(scan, Exception) else scan['errors'])
            return
        networks = scan['networks']
        rows = tui.wifi_rows(networks)
        choice = show_table_menu(t('tui_wifi'), ['SSID', t('tui_security'), t('tui_signal')], rows,
                                ['SSID: ' + row[0] + '\n' + row[1] for row in rows])
        if not 1 <= choice <= len(networks):
            return
        selected = networks[choice - 1]
    ssid = selected['ssid']
    secured = (selected.get('security') or '').strip().upper() not in ('', '--', 'OPEN')
    password = ''
    while True:
        if secured:
            password = input_dialog(t('tui_wifi'), 'SSID: ' + ssid, password=True,
                                    initial=password, background=background)
            if password is None:
                return
        def connect():
            ap_handler = ap.get_ap_handler()
            if ap_handler.is_ap_active() and not ap_handler.release_radio():
                network_handler.last_error_code = 'radio_busy'
                return False
            return network_handler.connect_wifi(ssid, password if secured else None)
        result, output = show_wait_screen(t('tui_wifi'), t('connecting_to', ssid=ssid), connect)
        if result is True:
            show_text_screen(t('tui_wifi'), [t('connected_to', ssid=ssid)])
            return
        code = getattr(network_handler, 'last_error_code', 'unknown')
        lines = wifi_error_lines(code, ssid)
        if code not in ('wrong_password', 'bad_password_format', 'auth_failed') or not secured:
            show_text_screen(t('tui_wifi_failed'), lines)
            return
        if not show_confirm_screen(t('tui_wifi_failed'), lines,
                                    yes_label=t('tui_edit_password'), no_label=t('tui_back')):
            return


def _power_action(action):
    """Use nonblocking systemd shutdown requests after explicit OK."""
    if not show_compact_confirmation(t('tui_' + action + '_confirm'),
                                    [t('tui_' + action + '_warning'), t('tui_connections_drop')],
                                    size=(54, 10)):
        return
    title = t('rebooting') if action == 'reboot' else t('tui_powering_off')
    result, output = show_wait_screen(title, title, run_command,
                                   ['systemctl', '--no-block', action], check=False, timeout=10)
    if isinstance(result, Exception) or not result or result[0] != 0:
        show_text_screen(t('tui_request_failed'), _output_lines(output) or [t('tui_request_failed')])
    else:
        show_power_pending(title)


def _reboot_prompt():
    """Release downloaded images and USB sources before this dialog is opened."""
    choice = show_horizontal_menu(t('flashing_success'), [t('return_menu'), t('reboot_now')])
    if choice == 2:
        _power_action('reboot')


def flash_to_device(image_path, cleanup=None):
    """Join exactly one protected writer and release its source before any dialog."""
    from flash import FlashHandler, select_target_device
    result = None
    output = ''
    try:
        target = select_target_device()
        if not target:
            return False
        handler = FlashHandler(emmc_device=target)
        if handler.confirm_flash(image_path) is not True:
            return False
        def worker(progress):
            progress(None, os.path.basename(image_path), target)
            return handler.flash_image(image_path, skip_confirmation=True, progress_cb=progress)
        result, output = show_progress_screen(t('title_flashing'), worker)
    finally:
        if cleanup:
            cleanup()
    if result is True:
        _reboot_prompt()
        return True
    show_text_screen(t('flashing_failed'), _output_lines(output, 15) or [t('flashing_failed_body')])
    return False


def flash_from_http():
    """Use the API directly; only the download worker receives a cancel token."""
    handler = DownloadHandler()
    try:
        handler.clear_cache()
    except (OSError, RuntimeError, ValueError) as exc:
        show_text_screen(t('title_download'), [str(exc)])
        return False
    free_space = check_disk_space(config.TEMP_DIR)
    if free_space < config.MIN_FREE_SPACE:
        show_text_screen(t('title_download'), [t('low_ram_space', space=format_bytes(free_space)),
                                               t('need_ram_space', space=format_bytes(config.MIN_FREE_SPACE))])
        return False
    downloaded = download_image_interactive(handler)
    if not downloaded:
        return False
    try:
        return flash_to_device(downloaded, cleanup=lambda:handler.discard_download(downloaded))
    finally:
        handler.discard_download(downloaded)


def flash_from_usb():
    """Unmount only a source mounted by this flow, after its writer has closed it."""
    handler = USBHandler()
    device = list_usb_devices_interactive()
    if not device:
        return False
    mounted_here = False
    def cleanup():
        nonlocal mounted_here
        if mounted_here:
            show_wait_screen('USB', t('tui_unmount'), handler.unmount_device)
            mounted_here = False
    try:
        mount_point = device.get('mountpoint')
        if not mount_point:
            result, output = show_wait_screen('USB', t('mounting_dev', device=device['device']),
                                            handler.mount_device, device['device'])
            if result is not True:
                show_text_screen('USB', [t('mount_usb_failed')]+_output_lines(output, 6))
                return False
            mounted_here = True
            mount_point = handler.mount_point
        images, output = show_wait_screen('USB', t('scanning_images'), handler.scan_for_images, mount_point)
        if isinstance(images, Exception) or not images:
            show_text_screen('USB', [t('no_images_on_usb')])
            return False
        rows = [(image['filename'], format_bytes(image['size'])) for image in images]
        choice = show_table_menu(t('source_usb'), [t('tui_image'), t('tui_size')], rows,
                               [image.get('relative_path') or image['filename'] for image in images])
        if not 1 <= choice <= len(images):
            return False
        return flash_to_device(images[choice - 1]['path'], cleanup=cleanup)
    finally:
        cleanup()


def flash_image_menu():
    """Choose JetHome images or USB; Esc returns to the main menu."""
    while True:
        choice = show_menu(t('tui_flash'), [t('tui_images'), t('tui_usb')])
        if not choice:
            return
        if (flash_from_http() if choice == 1 else flash_from_usb()):
            return


def _capacity(value):
    """Use total capacities, never free space on the RAM rootfs."""
    if not value:
        return '--'
    unit, divisor = ('GiB', 1024 ** 3) if value >= 1024 ** 3 else ('MiB', 1024 ** 2)
    return '{:.1f} {}'.format(value / divisor, unit)


def system_info_menu():
    """Read hardware capacities passively and show the recovery build and Web URLs."""
    info = get_recovery_info()
    memory = get_memory_info()
    endpoints = get_web_endpoints()
    lines = [t('device'), info.get('model') or '--', '', t('tui_memory'),
           'RAM: ' + _capacity(memory['ram_total'])+'    eMMC: ' + _capacity(memory['emmc_total']),
           '', t('tui_build'), info.get('firmware') or '--', '', t('tui_web')]
    for endpoint in endpoints:
        kind = {'ethernet': 'Ethernet', 'wifi': 'WiFi'}.get(endpoint['kind'])
        label = '{} ({})'.format(kind, endpoint['interface']) if kind else endpoint['interface']
        lines.append('{}: {}'.format(label, endpoint['url']))
    if not endpoints:
        lines.append(t('tui_no_address'))
    show_text_screen(t('tui_info'), lines)


def settings_menu():
    """Apply runtime language changes and group the two guarded power actions."""
    while True:
        language = 'English' if app_locale.get_language() == 'en' else 'Русский'
        choice = show_menu(t('settings'), [t('settings_language')+': ' + language, t('tui_power')])
        if not choice:
            return
        if choice == 1:
            selected = show_menu(t('settings_language'), ['English', 'Русский'])
            if selected:
                app_locale.set_language(('en', 'ru')[selected - 1])
        elif choice == 2:
            power = show_menu(t('tui_power'), [t('tui_reboot'), t('tui_poweroff')])
            if power:
                _power_action('reboot' if power == 1 else 'poweroff')


def main_menu():
    """Open the approved Classic menu with a read-only, inexpensive address header."""
    info = get_recovery_info()
    model = info.get('model') or config.JETHOME_DEVICE_NAME
    if model.startswith('JetHome '):
        model = model[8:]
    def address():
        urls = get_web_urls()
        return 'IP ' + urls[0].split('://', 1)[-1].rsplit(':', 1)[0] if urls else t('tui_no_address')
    tui.configure_header((info.get('firmware') or 'jrescue')+' | ' + model, address)
    while True:
        choice = show_menu(t('tui_main'), [t('tui_flash'), t('tui_network'), t('tui_info'), t('settings')], main=True)
        if choice:
            (flash_image_menu, network_setup_menu, system_info_menu, settings_menu)[choice - 1]()


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
    # Kiosk: the terminal-generated signals must not drop the user out of the
    # recovery UI. Ctrl+C (INT), Ctrl+\ (QUIT) and Ctrl+Z (TSTP) are ignored;
    # SIGTERM is left alone so systemd can still stop the service.
    for _sig in ('SIGINT', 'SIGQUIT', 'SIGTSTP'):
        try:
            signal.signal(getattr(signal, _sig), signal.SIG_IGN)
        except (AttributeError, ValueError, OSError):
            pass

    try:
        # Check root privileges
        require_root()

        app_locale.set_language('en')

        # Ensure directories exist
        ensure_directory(config.TEMP_DIR)
        ensure_directory(config.USB_MOUNT_POINT)

        # Clean up old temporary directory (migration from v1.2.1)
        cleanup_old_temp_dir()

        # Straight into the curses main menu — no plain-text banner
        run_console_ui(main_menu)

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
