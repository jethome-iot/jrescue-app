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


def network_menu(menu):
    """
    Network setup menu

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    items = [t("net_wifi"), t("net_ethernet")]

    while True:
        # Use select_from_list instead of show_menu for scrolling support and consistency
        choice = menu.select_from_list(t("net_title"), items, show_index=False,
                                       show_counter=False)

        if choice is None:
            return None  # Back
        elif choice == -1:
            return -1  # Home - go to main menu
        elif choice == 0:
            result = wifi_setup(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu
        elif choice == 1:
            result = ethernet_status(menu)
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
        result = menu.show_message(t("error"), "NetworkManager\nnot found")
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
        result = menu.show_message(t("wifi_title"), "No networks\nfound")
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
                # Failed - show error with OK button, then retry
                error_msg = f"{t('wifi_failed')}\n{ssid}\n{t('wifi_wrong_password')}"
                result = menu.show_message(t("error"), error_msg)
                if result == -1:
                    return -1  # Home
                # Loop will repeat password input
    else:
        # Open network - no password needed
        password = None
        success = menu.run_working(t("wifi_connecting"), ssid,
                                   handler.connect_wifi, ssid, password)

        if success:
            menu.show_message(t("wifi_connected"), f"{ssid}", wait_for_key=False, success=True)
            time.sleep(2)  # Show success message for 2 seconds
        else:
            menu.show_message(t("wifi_failed"), f"{ssid}")


def ethernet_status(menu):
    """Show wired link/IP details, independently of active Wi-Fi or the AP."""
    handler = get_network_handler()
    if not handler:
        return menu.show_message(t('error'), "NetworkManager\nnot found")
    devices = menu.run_working(t('net_ethernet'), t('wait'), handler.get_ethernet_status)
    if not devices:
        return menu.show_message(t('net_ethernet'), t('eth_missing'))
    if len(devices) > 1:
        choice = menu.select_from_list(t('net_ethernet'),
                                       [device['interface'] for device in devices],
                                       show_index=False, show_counter=False)
        if choice is None or choice == -1:
            return choice
        device = devices[choice]
    else:
        device = devices[0]
    carrier = device['carrier']
    link = t('eth_up') if carrier is True else t('eth_down') if carrier is False else '--'
    result = menu.show_network_status(t('net_ethernet'), device['interface'],
                                      t('eth_link') + ': ' + link, device['ip'] or '--')
    return -1 if result == -1 else None
