"""
System Information Screen for OLED
"""

import sys
import os

# Add parent dir to path for language import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t

# Add core/ to path to reuse modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from utils import get_system_info


def show_system_info(menu):
    """
    Display system information - simplified version
    Shows only firmware version and board name

    Args:
        menu: Menu instance

    Returns:
        -1 if HOME pressed, None otherwise
    """
    # Get system info
    info = get_system_info()

    # Extract firmware version from kernel or system
    version = info.get('kernel', 'Unknown')
    if 'Armbian' in version or 'armbian' in version.lower():
        # Try to extract just version number
        parts = version.split()
        for part in parts:
            if any(char.isdigit() for char in part):
                version = part[:13]  # Max 13 chars
                break
    else:
        version = version[:13]

    # Simple two-line display
    info_text = f"D2\n{version}"

    # Show info
    result = menu.show_message(t("info_title"), info_text, wait_for_key=True)
    return result  # Returns -1 if HOME pressed, None otherwise

