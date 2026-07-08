"""
Configuration file for Rescue Console Application
"""

import os
import re

# ==================== NETWORK SETTINGS ====================

JETHOME_API_BASE = "https://fw.jethome.com"

# JetHome device configuration.
JETHOME_BOARDS = {
    "j100": ("d1", "JetHub D1 (J100)"),
    "j200": ("d2", "JetHub D2 (J200)"),
    "j310": ("d3", "JetHub D3 (J310)"),
}


def _read_dt_model() -> str:
    """Return the board model string from the device tree (empty if unavailable)."""
    try:
        with open('/proc/device-tree/model', 'rb') as f:
            # device-tree strings are NUL-terminated
            return f.read().decode('utf-8', 'replace').replace('\x00', '').strip()
    except OSError:
        return ""


def detect_board():
    """Resolve (device_id, platform, name) for the fw.jethome.com REST API."""
    model = _read_dt_model()
    board = os.environ.get('BOARD', '')            # e.g. "jethub-j100"
    board_name = os.environ.get('BOARD_NAME', '')  # e.g. "JetHome JetHub J100"

    # platform, e.g. "j100" — from an explicit override, the recovery env vars,
    # or the device-tree model (first source yielding a "jNNN" code wins).
    platform = os.environ.get('JETHOME_PLATFORM')
    if not platform:
        for src in (board, board_name, model):
            m = re.search(r'j(\d+)', src, re.IGNORECASE)
            if m:
                platform = "j" + m.group(1)
                break

    # device id, e.g. "d1" — from an explicit override, the known-board map,
    # or the "Dx" token in the device-tree model.
    device = os.environ.get('JETHOME_DEVICE')
    if not device:
        if platform in JETHOME_BOARDS:
            device = JETHOME_BOARDS[platform][0]
        else:
            m = re.search(r'\bD(\d+)\b', model)  # "D1" -> d1
            if m:
                device = "d" + m.group(1)

    # Fallbacks for running off-hardware without any of the above
    platform = platform or "j100"
    device = device or JETHOME_BOARDS.get(platform, ("d1",))[0]
    name = board_name or model or JETHOME_BOARDS.get(platform, (None, "JetHub"))[1]
    return device, platform, name


JETHOME_DEVICE, JETHOME_PLATFORM, JETHOME_DEVICE_NAME = detect_board()

# Network interface fallbacks. NetworkManager devices are auto-detected at
# runtime (see core/network.py); these are only used if detection returns nothing.
WIFI_INTERFACE = "wlan0"
ETHERNET_INTERFACE = "eth0"

# Connection timeout in seconds
NETWORK_TIMEOUT = 10

# ==================== STORAGE SETTINGS ====================

# eMMC device path (check with: lsblk)
EMMC_DEVICE = "/dev/mmcblk1"

# Protected region at the start of the eMMC, in MiB.
# On JetHub eMMC-recovery boards the first RECOVERY_PROTECT_MB hold the
# bootloader, its environment and both A/B recovery slots. During normal boot
# u-boot hardware-write-protects this region, but INSIDE recovery it is WRITABLE,
# so the flasher itself must be the guard: a whole-disk OS image dd'd from
# sector 0 would otherwise destroy u-boot, its env and both recovery slots.
# The main-OS image is built with a matching offset (Armbian OFFSET=336), so we
# skip the image's first RECOVERY_PROTECT_MB and write the rest at the same
# absolute offset, preserving the boot area, recovery slots and the on-eMMC
# partition table. Assumes a full-disk source image. Set to 0 to flash a plain
# full-disk image from sector 0 (non-recovery targets, e.g. a blank SD card).
RECOVERY_PROTECT_MB = 336

# Temporary directory for downloads
TEMP_DIR = "/tmp/rescue"

# USB mount point
USB_MOUNT_POINT = "/mnt/usb"

MIN_FREE_SPACE = 600 * 1024 * 1024

# ==================== APPLICATION SETTINGS ====================

# Application version
APP_VERSION = "1.3.1"

# Enable verbose console output (info messages, progress, etc.)
# Set to False to minimize console output
VERBOSE_LOGS = True

# Completely disable all console output (print_*, etc.)
# Used by OLED and Web applications
SILENT_CONSOLE = False

# Use interactive menu with arrow keys (requires curses support)
# Set to False for classic numbered menu
INTERACTIVE_MENU = True

# ==================== ADVANCED SETTINGS ====================

# Block size for dd command (in MB)
DD_BLOCK_SIZE = 4  # 4MB blocks

# Chunk size for downloads (bytes)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB

# ==================== SAFETY SETTINGS ====================

# Skip mount check (DANGEROUS! Only for testing when running from eMMC)
# WARNING: Setting this to True allows flashing eMMC while system is running from it
# This WILL corrupt the running system! Only use for testing purposes!
SKIP_MOUNT_CHECK = False  # Set to True only for testing on a non-recovery host

