"""
Configuration file for Rescue Web Application

This module imports shared configuration from core/config.py and overrides
settings specific to the web interface. All core settings are available,
with web-specific overrides applied.
"""

# Standard library imports
import os
import sys
import importlib.util

# Web server settings
WEB_SERVER_HOST = "0.0.0.0"  # Listen on all interfaces
WEB_SERVER_PORT = 8124       # HTTP port
STATIC_DIR = "static"         # Static files directory

# Import settings from core
_core_path = os.path.join(os.path.dirname(__file__), '../core')
sys.path.insert(0, _core_path)

# Import core config module dynamically
spec = importlib.util.spec_from_file_location(
    "core_config",
    os.path.join(_core_path, "config.py")
)
core_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_config)

# Copy all settings from core config
# This makes all core configuration available in this module
for attr in dir(core_config):
    if not attr.startswith('_'):
        globals()[attr] = getattr(core_config, attr)

# ==================== WEB-SPECIFIC OVERRIDES ====================

# Override settings for web interface
INTERACTIVE_MENU = False  # Disable curses menu for web
SILENT_CONSOLE = True      # Disable console output (use logging instead)
VERBOSE_LOGS = False       # Disable verbose logging for web service

# ==================== WEB-SPECIFIC SETTINGS ====================

# Session timeout (for future use)
SESSION_TIMEOUT = 3600  # 1 hour

# Maximum upload size for USB images
MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10GB

# Note: Logs are disabled by default (SILENT_CONSOLE=True, VERBOSE_LOGS=False)
# If you need logs, enable them in the settings above and set LOG_FILE path