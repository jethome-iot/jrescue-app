"""
Configuration file for OLED Rescue Console Application
"""

# ==================== OLED DISPLAY SETTINGS ====================

# Framebuffer Settings (OLED managed by kernel driver ssd130x-i2c)
FRAMEBUFFER_DEVICE = '/dev/fb0'  # Linux framebuffer device for OLED
OLED_WIDTH = 128
OLED_HEIGHT = 64

# ==================== DISPLAY SETTINGS ====================

# Display Settings
FONT_SMALL = 12   # For menu items (readable)
FONT_NORMAL = 14  # For titles

# Fallback font paths (try in order)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf"
]

# Text Settings
MAX_LINE_LENGTH = 18  # Characters per line at font size 12 (128px / 7px per char)
TEXT_TRUNCATE = "..."

# ==================== DEVICE SETTINGS ====================

# Board device id / platform is auto-detected in core config
# (env override -> /proc/device-tree/model -> fallback). This app no longer
# overrides it, so the right images are pulled for whatever board it runs on.

# Hardware devices
EMMC_DEVICE = "/dev/mmcblk1"
WIFI_INTERFACE = "wlan0"
ETHERNET_INTERFACE = "eth0"
USB_MOUNT_POINT = "/mnt/usb"

# Storage paths (tmpfs = RAM, не изнашивает flash и быстрее)
TEMP_DIR = "/tmp/rescue"

# JetHome API
JETHOME_API_BASE = "https://fw.jethome.com"

# Network
NETWORK_TIMEOUT = 30

# Download settings
DD_BLOCK_SIZE = 4  # MB
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB

# Advanced settings
SKIP_MOUNT_CHECK = False  # Only True for testing on a non-recovery host
SILENT_CONSOLE = True  # Disable all console output (logs only to file)
VERBOSE_LOGS = False  # Disable verbose logging

# ==================== INPUT SETTINGS ====================

# GPIO Buttons (from device tree)
# Will use evdev to read /dev/input/eventX
BUTTON_DEBOUNCE_MS = 100

# Test mode (set to True to run without physical buttons)
TEST_MODE_NO_BUTTONS = False  # Set to True for testing without gpio-keys

# ==================== APPLICATION SETTINGS ====================

# Application name (version comes from core config — single source of truth)
APP_NAME = "Rescue"

