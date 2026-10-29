"""
Configuration file for OLED Rescue Console Application
"""

import importlib.util
import os

# Core modules can resolve `import config` to this module. Inherit shared
# settings rather than maintaining a second, incomplete set of safety flags.
_core_config_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'config.py')
_spec = importlib.util.spec_from_file_location('oled_core_config', _core_config_path)
_core_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core_config)
for _name in dir(_core_config):
    if _name.isupper():
        globals()[_name] = getattr(_core_config, _name)

# ==================== OLED DISPLAY SETTINGS ====================

# Framebuffer Settings (OLED managed by kernel driver ssd130x-i2c)
FRAMEBUFFER_DEVICE = '/dev/fb0'  # Linux framebuffer device for OLED
OLED_WIDTH = 128
OLED_HEIGHT = 64

# ==================== DISPLAY SETTINGS ====================

# Keep the approved main grid independent of inner-screen typography.
MAIN_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/TTF/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansCondensed.ttf"
]
_font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
FONT_PATHS = [os.path.join(_font_dir, 'LiberationSans-Regular.ttf')] + MAIN_FONT_PATHS
KEYBOARD_FONT_PATHS = [os.path.join(_font_dir, 'LiberationSansNarrow-Regular.ttf')] + FONT_PATHS
FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansCondensed-Bold.ttf"
]
OLED_ANIMATION_FPS = 8

# ==================== OLED-SPECIFIC OVERRIDES ====================

NETWORK_TIMEOUT = 30
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

