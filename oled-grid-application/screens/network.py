"""
Network Setup Screen for OLED
"""

import sys
import os

# Add parent dir to path for language import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t

# Add core/ to path to reuse modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from network import get_network_handler
import time


def wifi_error_message(code):
    """Keep the cause and next step in the display's two visible body rows."""
    reason, hint = {
        'wrong_password': ('wifi_wrong_password', 'wifi_enter_again'),
        'bad_password_format': ('wifi_bad_password', 'wifi_enter_again'),
        'auth_failed': ('wifi_auth_failed', 'wifi_check_password'),
        'not_found': ('wifi_not_found', 'wifi_scan_again'),
        'no_dhcp': ('wifi_no_dhcp', 'wifi_check_router'),
        'timeout': ('wifi_timeout', 'wifi_try_again'),
        'radio_busy': ('wifi_radio_busy', 'wifi_check_adapter'),
        'no_wifi': ('wifi_no_adapter', 'wifi_check_adapter'),
        'unavailable': ('wifi_unavailable', 'wifi_restart'),
    }.get(code, ('wifi_connect_failed', 'wifi_try_again'))
    return t(reason)+'\n'+t(hint)


def _wifi_error(menu, handler=None, code=None):
    """Show the diagnosis first instead of hiding it behind a long SSID."""
    code = code or getattr(handler, 'last_error_code', 'unknown')
    return menu.show_message(t('wifi_failed'), wifi_error_message(code))


def network_menu(menu):
    """
    Network setup menu

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    items = [t("net_wifi"), t("net_status")]

    while True:
        # Use select_from_list instead of show_menu for scrolling support and consistency
        choice = menu.select_from_list(t("net_title"), items, show_index=False,
                                       show_counter=True)

        if choice is None:
            return None  # Back
        elif choice == -1:
            return -1  # Home - go to main menu
        elif choice == 0:
            result = wifi_setup(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu
        elif choice == 1:
            result = network_status(menu)
            if result == -1:
                return -1


def wifi_setup(menu):
    """
    WiFi setup screen

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    # Get network handler
    handler = get_network_handler()
    if not handler:
        result = _wifi_error(menu, code='unavailable')
        if result == -1:
            return -1  # Home
        return None  # Back

    # The radio is single: while the setup-AP holds it nothing can be scanned or
    # joined, so hand it back to NetworkManager before doing anything else.
    import ap as ap_module
    ap_handler = ap_module.get_ap_handler()
    if ap_handler.is_ap_active():
        menu.run_working(t("wifi_title"), t("ap_stopping"), ap_handler.release_radio)

    networks = menu.run_working(t("wifi_title"), t("wifi_scanning"), handler.scan_wifi)

    if not networks:
        if getattr(handler, 'last_error_code', ''):
            result = _wifi_error(menu, handler)
        else:
            result = menu.show_message(t('wifi_title'), t('wifi_no_networks')+'\n'+t('wifi_scan_again'))
        if result == -1:
            return -1  # Home
        return None  # Back

    # Build network list (no truncation - text wraps automatically)
    ssids = [net['ssid'] for net in networks]

    # Select network (with counter to show total number of networks)
    selected = menu.select_from_list(t("wifi_select"), ssids, show_index=True,
                                     show_counter=True, compact=True)

    if selected is None:
        return None  # Cancelled
    elif selected == -1:
        return -1  # Home

    network = networks[selected]
    ssid = network['ssid']

    # Check if network is secured
    if network['security'] != "Open":
        # Loop for password retry on failure
        while True:
            # Selecting a secured network opens the editor directly.
            password = menu.input_text(t("wifi_password"), "")

            if password is None:
                return None  # Cancelled
            elif password == -1:
                return -1  # Home

            # Connect
            success = menu.run_working(t("wifi_connecting"), ssid,
                                       handler.connect_wifi, ssid, password)

            if success:
                # Success - show message for 2 seconds and return to Network menu
                menu.show_message(t("wifi_connected"), f"{ssid}", wait_for_key=False, success=True)
                time.sleep(2)  # Show success message for 2 seconds
                return  # Exit to Network menu
            else:
                result = _wifi_error(menu, handler)
                if result == -1:
                    return -1  # Home
                if getattr(handler, 'last_error_code', '') not in (
                        'wrong_password', 'bad_password_format', 'auth_failed'):
                    return None
    else:
        # Open network - no password needed
        password = None
        success = menu.run_working(t("wifi_connecting"), ssid,
                                   handler.connect_wifi, ssid, password)

        if success:
            menu.show_message(t("wifi_connected"), f"{ssid}", wait_for_key=False, success=True)
            time.sleep(2)  # Show success message for 2 seconds
        else:
            return _wifi_error(menu, handler)


def network_status_page(device):
    """Describe one interface using the existing two-row status layout."""
    title = 'Ethernet' if device['kind'] == 'ethernet' else 'WiFi'
    if device.get('state') is None or device['state'] in (10, 20):
        key = 'net_unavailable'
    elif device['kind'] == 'ethernet' and device.get('carrier') is False:
        key = 'net_no_cable'
    elif device.get('connected') and device.get('ip'):
        key = ('net_internet_yes' if device.get('internet') is True else
               'net_internet_no' if device.get('internet') is False else 'net_internet_unknown')
    elif device.get('carrier') is True or device['state'] in (70, 80, 90, 100):
        key = 'net_no_ip'
    else:
        key = 'net_disconnected'
    return {'title': title, 'interface': device['interface'],
            'status': t(key), 'ip': device.get('ip') or '--'}


def network_status(menu):
    """Page through all detected interfaces; Enter refreshes the snapshot."""
    handler = menu.run_working(t('net_status'), t('wait'), get_network_handler)
    if not handler:
        return menu.show_message(t('net_status'), t('net_unavailable'))
    selected = 0
    while True:
        devices = menu.run_working(t('net_status'), t('wait'), handler.get_network_status,
                                   check_internet=True)
        if not devices:
            return menu.show_message(t('net_status'), t('net_unavailable') if handler.last_error
                                     else t('net_no_interfaces'))
        pages = [network_status_page(device) for device in devices]
        action, selected = menu.show_network_pages(pages, initial=selected)
        if action is not True:
            return action
