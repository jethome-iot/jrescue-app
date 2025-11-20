"""
Configuration file for Rescue Console Application
"""

# ==================== NETWORK SETTINGS ====================

# Default HTTP server for downloading images
# Only used when JETHOME_API_ENABLED = False
# Example: "http://192.168.1.100:8000" (use example_server.py to host images)
DEFAULT_SERVER = ""

# JetHome API settings (for automatic firmware discovery)
JETHOME_API_ENABLED = True
JETHOME_API_BASE = "https://fw.jethome.com"

# JetHome device configuration (fixed: only D2 supported)
JETHOME_DEVICE_NAME = "JetHub D2"
JETHOME_DEVICE = "d2"  # Device identifier for API
JETHOME_PLATFORM = "j200"  # Platform identifier

# Network interfaces
WIFI_INTERFACE = "wlan0"
ETHERNET_INTERFACE = "eth0"

# Connection timeout in seconds
NETWORK_TIMEOUT = 10

# ==================== STORAGE SETTINGS ====================

# eMMC device path (check with: lsblk)
EMMC_DEVICE = "/dev/mmcblk1"

# Temporary directory for downloads
# Для rescue систем используем /tmp (обычно tmpfs в RAM, очищается при перезагрузке)
# Образы загружаются в RAM, затем распаковываются потоком через xzcat прямо в eMMC
# Если система не read-only и есть место на диске, можно изменить на /var/rescue
TEMP_DIR = "/tmp/rescue"

# USB mount point
USB_MOUNT_POINT = "/mnt/usb"

# Minimum free space required in RAM (in bytes) - 600MB
# Нужно только для хранения СЖАТОГО образа .img.xz
# Распаковка идёт потоком через xzcat прямо в eMMC, не требует дополнительного места
MIN_FREE_SPACE = 600 * 1024 * 1024

# ==================== IMAGE SETTINGS ====================

# Available images list (used only when JETHOME_API_ENABLED = False)
# When JetHome API is enabled, this list is ignored
# Format: {"name": "Display Name", "filename": "image.img.xz", "size_mb": 1024}
AVAILABLE_IMAGES = [
    # Добавьте свои образы здесь, если отключите JetHome API
    # Пример:
    # {
    #     "name": "Custom Image",
    #     "filename": "custom-image.img.xz",
    #     "size_mb": 2048,
    #     "description": "Custom description"
    # }
]

# JetHome firmware types to show (filter by these keys)
# Set to None to show all available firmware types
JETHOME_FIRMWARE_FILTER = [
    "armbian.nightly.trixie.edge",
    "armbian.nightly.jammy.edge",
    "armbian.nightly.noble.edge",
    "armbian.nightly.bookworm.edge",
    "jhaos.release"
]

# ==================== APPLICATION SETTINGS ====================

# Application name
APP_NAME = "Rescue Console Application"
APP_VERSION = "1.3.0"

# Enable debug logging
DEBUG = False

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

# Number of retries for network operations
NETWORK_RETRY_COUNT = 3

# Delay between retries (seconds)
RETRY_DELAY = 5

# Chunk size for downloads (bytes)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB

# USB detection timeout (seconds)
USB_DETECTION_TIMEOUT = 30

# ==================== SAFETY SETTINGS ====================

# Skip mount check (DANGEROUS! Only for testing when running from eMMC)
# WARNING: Setting this to True allows flashing eMMC while system is running from it
# This WILL corrupt the running system! Only use for testing purposes!
SKIP_MOUNT_CHECK = True  # Set to False for production use!

