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


def _read_os_release() -> dict:
    """
    Read /etc/os-release into a dict.
    Prefer PRETTY_NAME for display.
    """
    data = {}
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k] = v.strip().strip('"')
    except Exception:
        pass
    return data


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

    # Prefer os-release (patched in post-build) for product name/version
    osr = _read_os_release()
    pretty = osr.get("PRETTY_NAME")
    if not pretty:
        name = osr.get("NAME", "jrescue")
        ver = osr.get("VERSION_ID", "")
        pretty = f"{name} {ver}".strip()

    # Fallback: show kernel version if os-release is missing
    if not pretty:
        pretty = info.get("kernel", "Unknown")[:18]

    # Keep it simple and readable on 128x64: 2 lines max
    info_text = pretty[:18]

    # Show info
    result = menu.show_message(t("info_title"), info_text, wait_for_key=True)
    return result  # Returns -1 if HOME pressed, None otherwise

