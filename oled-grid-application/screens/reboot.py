"""
Reboot Screen for OLED
"""

import sys
import os
import time

# Add parent dir to path for language import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t


def reboot_system(menu):
    """
    Reboot confirmation and execution

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    # First confirmation
    result = menu.confirm(t("reboot_confirm"), "")
    if result == -1:
        return -1  # Home
    elif not result:
        return None  # Cancelled

    # Second confirmation for safety
    result = menu.confirm(t("reboot_confirm"), t("yes") + "?")
    if result == -1:
        return -1  # Home
    elif not result:
        return None  # Cancelled

    # Show rebooting message
    menu.show_message(t("reboot_wait"), "", wait_for_key=False)
    time.sleep(2)

    # Execute reboot
    os.system('reboot')

