"""
Configuration file for Rescue Web Application
"""

import sys
import os

# Web server settings
WEB_SERVER_HOST = "0.0.0.0"  # Listen on all interfaces
WEB_SERVER_PORT = 8124
STATIC_DIR = "static"

# Import settings from core
_core_path = os.path.join(os.path.dirname(__file__), '../core')
sys.path.insert(0, _core_path)

# Import core config module
import importlib.util
spec = importlib.util.spec_from_file_location("core_config", os.path.join(_core_path, "config.py"))
core_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_config)

# Copy all settings from core config
for attr in dir(core_config):
    if not attr.startswith('_'):
        globals()[attr] = getattr(core_config, attr)

# Override settings for web interface
INTERACTIVE_MENU = False  # Disable curses menu for web
SILENT_CONSOLE = True  # Disable console output (use logging instead)
VERBOSE_LOGS = False  # Disable verbose logging for web service

# Web-specific settings
# Logs are disabled by default (SILENT_CONSOLE=True, VERBOSE_LOGS=False)
# If you need logs, enable them in the settings above and set LOG_FILE path
SESSION_TIMEOUT = 3600  # 1 hour (for future use)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10GB (for USB images)