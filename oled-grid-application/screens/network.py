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
    items = [t("net_wifi"), t("net_ap"), t("net_test")]

    while True:
        # Use select_from_list instead of show_menu for scrolling support and consistency
        choice = menu.select_from_list(t("net_title"), items, show_index=False, show_counter=False)

        if choice is None:
            return None  # Back
        elif choice == -1:
            return -1  # Home - go to main menu
        elif choice == 0:
            result = wifi_setup(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu
        elif choice == 1:
            result = ap_setup(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu
        elif choice == 2:
            result = test_connectivity(menu)
            if result == -1:
                return -1  # Propagate HOME to main menu


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

    # Show scanning message
    menu.show_working(t("wifi_title"), t("wifi_scanning"), 0)

    # Scan for networks
    networks = handler.scan_wifi()

    if not networks:
        result = menu.show_message(t("wifi_title"), "No networks\nfound")
        if result == -1:
            return -1  # Home
        return None  # Back

    # Build network list (no truncation - text wraps automatically)
    ssids = [net['ssid'] for net in networks]

    # Select network (with counter to show total number of networks)
    selected = menu.select_from_list(t("wifi_select"), ssids, show_index=True, show_counter=True)

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
            # Ask for password confirmation with horizontal choice
            title = f"{ssid[:15]}\n{t('wifi_password')}?"
            choice = menu.horizontal_choice(title, "NO", "OK")

            if choice is None or choice == 0:
                return None  # Cancelled or NO selected
            elif choice == -1:
                return -1  # Home

            # Get password
            password = menu.input_text(t("wifi_password"), "")

            if password is None:
                return None  # Cancelled
            elif password == -1:
                return -1  # Home

            # Connect
            menu.show_working(t("wifi_connecting"), f"{ssid[:18]}", 0)
            success = handler.connect_wifi(ssid, password)

            if success:
                # Success - show message for 2 seconds and return to Network menu
                menu.show_message(t("wifi_connected"), f"{ssid[:18]}", wait_for_key=False)
                time.sleep(2)  # Show success message for 2 seconds
                return  # Exit to Network menu
            else:
                # Failed - show error with OK button, then retry
                error_msg = f"{t('wifi_failed')}\n{ssid[:15]}\n{t('wifi_wrong_password')}"
                result = menu.show_message(t("error"), error_msg)
                if result == -1:
                    return -1  # Home
                # Loop will repeat password input
    else:
        # Open network - no password needed
        password = None
        menu.show_working(t("wifi_connecting"), f"{ssid[:18]}", 0)
        success = handler.connect_wifi(ssid, password)

        if success:
            menu.show_message(t("wifi_connected"), f"{ssid[:18]}", wait_for_key=False)
            time.sleep(2)  # Show success message for 2 seconds
        else:
            menu.show_message(t("wifi_failed"), f"{ssid[:18]}")


def ap_setup(menu):
    """
    Raise the Wi-Fi setup-AP and show a join-QR so a phone can provision the
    device via the web portal (http://10.42.0.1). Scanning the QR joins the AP;
    the phone's captive portal then pops the setup page.

    Returns:
        -1 if HOME pressed, None otherwise
    """
    import ap as ap_module
    from input import KEY_HOME

    handler = ap_module.get_ap_handler()

    menu.show_working(t("net_ap"), t("ap_start"), 0)
    if not handler.is_ap_active():
        handler.start_ap()

    # jrescue-ap-up writes the creds file early but waits for the (USB) radio to
    # enumerate — poll briefly so we can encode the SSID/PSK into the QR.
    creds = {}
    for _ in range(20):
        creds = handler.read_creds()
        if creds.get('ssid'):
            break
        time.sleep(0.5)

    if not handler.is_ap_active():
        result = menu.show_message(t("error"), t("ap_fail"))
        return -1 if result == -1 else None

    ssid = creds.get('ssid') or 'jethub'
    psk = creds.get('psk') or 'jethub123'
    url = (creds.get('url') or 'http://10.42.0.1').replace('http://', '')

    _draw_ap_qr(menu.display, ssid, psk, url)

    # Hold the QR on screen until any key; HOME propagates to the main menu.
    key = menu.input.wait_for_key()
    return -1 if key == KEY_HOME else None


def _draw_ap_qr(display, ssid, psk, url):
    """Render a Wi-Fi join-QR (left) + SSID/PSK/URL text (right) on the OLED.

    The QR encodes a standard WIFI: payload so a phone camera joins the AP
    directly. It is drawn dark-on-light (light = lit OLED pixels) because most
    scanners expect a light background; a plain text panel is shown if the
    optional `qrcode` package is unavailable.
    """
    from PIL import Image, ImageDraw

    display.image = Image.new('1', (display.width, display.height), color=0)
    display.draw = ImageDraw.Draw(display.image)
    d = display.draw
    font = display.font_small

    qr_size = 0
    try:
        import qrcode
        payload = "WIFI:T:WPA;S:%s;P:%s;;" % (ssid, psk)
        qr = qrcode.QRCode(border=1, box_size=1)
        qr.add_data(payload)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        n = len(matrix)
        scale = max(1, min(display.height, 64) // n)
        qr_size = n * scale
        # Light (lit) background so the dark modules read on the OLED.
        d.rectangle((0, 0, qr_size - 1, qr_size - 1), fill=1)
        for ry, row in enumerate(matrix):
            for rx, bit in enumerate(row):
                if bit:
                    x0 = rx * scale
                    y0 = ry * scale
                    d.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill=0)
    except Exception:
        qr_size = 0  # qrcode missing or failed — fall back to text only

    tx = qr_size + 3 if qr_size else 2
    avail_chars = max(1, (display.width - tx) // 7)
    y = 1
    for line in (ssid, psk, url):
        d.text((tx, y), display._truncate(str(line), avail_chars), font=font, fill=1)
        y += 13

    display._update_display()


def test_connectivity(menu):
    """
    Test connectivity to JetHome API

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    handler = get_network_handler()
    if not handler:
        result = menu.show_message(t("error"), "NetworkManager\nnot found")
        if result == -1:
            return -1  # Home
        return None  # Back

    # Show testing message
    menu.show_working(t("net_test"), t("wait"), 0)
    time.sleep(0.5)

    # Get all interfaces
    interfaces = handler.get_all_interfaces()

    if not interfaces:
        result = menu.show_message(t("error"), "No active\nconnections")
        if result == -1:
            return -1  # Home
        return None  # Back

    # Build list of interface info strings for selection
    # Format: interface on first line, IP on second line (no indent)
    interface_items = []
    for iface in interfaces:
        if iface['ssid']:
            # WiFi with SSID - interface, IP, then SSID
            interface_items.append(f"{iface['interface']}:\n{iface['ip']} {iface['ssid']}")
        else:
            # Ethernet or WiFi without SSID - interface, then IP
            interface_items.append(f"{iface['interface']}:\n{iface['ip']}")

    # Show list with scroll and numbering (if more than 1 interface)
    if len(interface_items) == 1:
        # Single interface - show directly
        menu.show_message(t("net_test"), interface_items[0])
    else:
        # Multiple interfaces - show as scrollable list
        selected = menu.select_from_list(t("net_test"), interface_items)
        # User just views the list, no action needed
        # But if HOME pressed (-1), exit to main menu
        if selected == -1:
            return -1  # Home

