"""
API Handler for Rescue Web Application
Implements REST API endpoints for network, flash, USB, and system operations
"""

import json
import os
import sys
import threading
import time
import traceback

# Add core directory to path
_core_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core')
sys.path.insert(0, _core_path)

# Import from core
import config
import network
import download
import flash
import usb
from utils import get_system_info, check_disk_space, get_device_size, format_bytes

# Global state for long-running operations
operation_state = {
    'download': {
        'active': False,
        'progress': 0,
        'total': 0,
        'speed': 0,
        'eta': 0,
        'error': None,
        'filename': None,
        'path': None
    },
    'flash': {
        'active': False,
        'progress': 0,
        'error': None,
        'status': 'idle'  # idle, flashing, complete
    }
}

# Handlers
network_handler = None
download_handler = None
flash_handler = None
usb_handler = None

def init_handlers():
    """Initialize all handlers"""
    global network_handler, download_handler, flash_handler, usb_handler
    if network_handler is None:
        network_handler = network.get_network_handler()
        download_handler = download.DownloadHandler()
        flash_handler = flash.FlashHandler()
        usb_handler = usb.USBHandler()

class APIHandler:
    """REST API request handler"""

    def __init__(self):
        init_handlers()

    # ==================== NETWORK OPERATIONS ====================

    def get_network_status(self):
        """GET /api/network/status - Get current network status"""
        try:
            interfaces = network_handler.get_all_interfaces()
            current = network_handler.get_connection_status()

            return {
                'success': True,
                'interfaces': interfaces,
                'current': current
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def post_wifi_scan(self):
        """POST /api/network/wifi/scan - Scan for WiFi networks"""
        try:
            networks = network_handler.scan_wifi()
            return {
                'success': True,
                'networks': networks
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def post_wifi_connect(self, data):
        """POST /api/network/wifi/connect - Connect to WiFi"""
        try:
            ssid = data.get('ssid')
            password = data.get('password', '')

            if not ssid:
                return {'success': False, 'error': 'SSID is required'}

            success = network_handler.connect_wifi(ssid, password)

            if success:
                # Wait a bit for connection to establish
                time.sleep(2)
                status = network_handler.get_connection_status()
                return {
                    'success': True,
                    'message': f'Connected to {ssid}',
                    'status': status
                }
            else:
                return {'success': False, 'error': 'Failed to connect'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Ethernet connects automatically via DHCP when cable is plugged in
    # No manual connection endpoint needed - status shown via get_status()

    def get_network_test(self):
        """GET /api/network/test - Test connectivity"""
        try:
            success = network_handler.test_connectivity()
            return {
                'success': True,
                'connected': success,
                'message': 'Internet connection OK' if success else 'No internet connection'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== FLASH OPERATIONS ====================

    def get_flash_images(self):
        """GET /api/flash/images - List available images"""
        try:
            images = []

            # Get JetHome API images
            if config.JETHOME_API_ENABLED:
                try:
                    jethome_images = download_handler.fetch_jethome_images()
                    for img in jethome_images:
                        images.append({
                            'source': 'jethome',
                            'name': img.get('name', 'Unknown'),
                            'version': img.get('version', 'N/A'),
                            'date': img.get('date', 'N/A'),
                            'size': img.get('size', 0),
                            'url': img.get('url', ''),
                            'filename': img.get('filename', '')
                        })
                except Exception as e:
                    print(f"Failed to fetch JetHome images: {e}")

            return {
                'success': True,
                'images': images
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def post_flash_download(self, data):
        """POST /api/flash/download - Start download"""
        global operation_state

        try:
            if operation_state['download']['active']:
                return {'success': False, 'error': 'Download already in progress'}

            url = data.get('url')
            filename = data.get('filename')
            size = data.get('size', 0)  # Expected file size

            if not url or not filename:
                return {'success': False, 'error': 'URL and filename are required'}

            # Reset state
            operation_state['download'] = {
                'active': True,
                'progress': 0,
                'total': size,
                'speed': 0,
                'eta': 0,
                'error': None,
                'filename': filename,
                'path': None
            }

            # Start download in background thread
            def download_thread():
                try:
                    path = download_handler.download_file(url, dest_filename=filename)
                    operation_state['download']['path'] = path
                    operation_state['download']['active'] = False
                    operation_state['download']['progress'] = operation_state['download']['total']
                except Exception as e:
                    operation_state['download']['error'] = str(e)
                    operation_state['download']['active'] = False

            thread = threading.Thread(target=download_thread, daemon=True)
            thread.start()

            return {
                'success': True,
                'message': 'Download started',
                'filename': filename
            }

        except Exception as e:
            operation_state['download']['active'] = False
            return {'success': False, 'error': str(e)}

    def get_flash_progress(self):
        """GET /api/flash/progress - Get download/flash progress"""
        global operation_state

        try:
            # Update download progress from temp file
            if operation_state['download']['active']:
                filename = operation_state['download']['filename']

                if filename:
                    temp_path = os.path.join(config.TEMP_DIR, filename + '.partial')
                    if os.path.exists(temp_path):
                        current_size = os.path.getsize(temp_path)
                        # Store current size in bytes (JS will calculate percentage)
                        operation_state['download']['progress'] = current_size

            return {
                'success': True,
                'download': operation_state['download'],
                'flash': operation_state['flash']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def post_flash_start(self, data):
        """POST /api/flash/start - Start flashing"""
        global operation_state

        try:
            if operation_state['flash']['active']:
                return {'success': False, 'error': 'Flash operation already in progress'}

            image_path = data.get('path')
            if not image_path:
                return {'success': False, 'error': 'Image path is required'}

            if not os.path.exists(image_path):
                return {'success': False, 'error': 'Image file not found'}

            # Reset state
            operation_state['flash'] = {
                'active': True,
                'progress': 0,
                'error': None,
                'status': 'flashing'
            }

            # Start flash in background thread
            def flash_thread():
                try:
                    success = flash_handler.flash_image(image_path, verify=False, skip_confirmation=True)
                    if success:
                        operation_state['flash']['status'] = 'complete'
                        operation_state['flash']['progress'] = 100
                    else:
                        operation_state['flash']['error'] = 'Flash failed'
                        operation_state['flash']['status'] = 'error'
                except Exception as e:
                    operation_state['flash']['error'] = str(e)
                    operation_state['flash']['status'] = 'error'
                finally:
                    operation_state['flash']['active'] = False

            thread = threading.Thread(target=flash_thread, daemon=True)
            thread.start()

            return {
                'success': True,
                'message': 'Flashing started'
            }

        except Exception as e:
            operation_state['flash']['active'] = False
            return {'success': False, 'error': str(e)}

    def delete_flash_cancel(self):
        """DELETE /api/flash/cancel - Cancel current operation"""
        global operation_state

        try:
            # Cancel download - remove partial file
            if operation_state['download']['active']:
                filename = operation_state['download'].get('filename')
                if filename:
                    temp_path = os.path.join(config.TEMP_DIR, filename + '.partial')
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                operation_state['download'] = {
                    'active': False,
                    'progress': 0,
                    'total': 0,
                    'speed': 0,
                    'eta': 0,
                    'error': 'Canceled by user',
                    'filename': None,
                    'path': None
                }

            # Cancel flash (can't really stop dd, just mark as canceled)
            if operation_state['flash']['active']:
                operation_state['flash']['error'] = 'Canceled by user'
                operation_state['flash']['active'] = False

            return {
                'success': True,
                'message': 'Operation canceled'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_flash_files(self):
        """GET /api/flash/files - Get list of downloaded files"""
        try:
            files = []
            if not os.path.exists(config.TEMP_DIR):
                return {'success': True, 'files': files}

            # List image files (.img.xz, .xz, .img) except .partial
            for filename in os.listdir(config.TEMP_DIR):
                # Skip partial downloads
                if filename.endswith('.partial'):
                    continue

                # Only show image files
                if not filename.endswith(('.img.xz', '.xz', '.img')):
                    continue

                filepath = os.path.join(config.TEMP_DIR, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append({
                        'filename': filename,
                        'path': filepath,
                        'size': stat.st_size,
                        'size_human': format_bytes(stat.st_size),
                        'modified': stat.st_mtime
                    })

            # Sort by modification time (newest first)
            files.sort(key=lambda x: x['modified'], reverse=True)

            return {
                'success': True,
                'files': files
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_flash_file(self, data):
        """DELETE /api/flash/file - Delete a downloaded file"""
        try:
            filepath = data.get('path')
            if not filepath:
                return {'success': False, 'error': 'File path is required'}

            # Security check - must be in TEMP_DIR
            if not filepath.startswith(config.TEMP_DIR):
                return {'success': False, 'error': 'Invalid file path'}

            if not os.path.exists(filepath):
                return {'success': False, 'error': 'File not found'}

            os.remove(filepath)

            return {
                'success': True,
                'message': f'File deleted: {os.path.basename(filepath)}'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== USB OPERATIONS ====================

    def get_usb_status(self):
        """GET /api/usb/status - Check USB device status"""
        try:
            device = usb_handler.detect_usb()

            if device:
                return {
                    'success': True,
                    'connected': True,
                    'device': device
                }
            else:
                return {
                    'success': True,
                    'connected': False,
                    'device': None
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def post_usb_mount(self):
        """POST /api/usb/mount - Mount USB drive"""
        try:
            success = usb_handler.mount_usb()

            if success:
                return {
                    'success': True,
                    'message': f'USB mounted at {config.USB_MOUNT_POINT}'
                }
            else:
                return {'success': False, 'error': 'Failed to mount USB'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_usb_images(self):
        """GET /api/usb/images - List images on USB"""
        try:
            images = usb_handler.scan_images()

            if images:
                formatted_images = []
                for img in images:
                    formatted_images.append({
                        'source': 'usb',
                        'name': os.path.basename(img),
                        'path': img,
                        'size': os.path.getsize(img) if os.path.exists(img) else 0
                    })

                return {
                    'success': True,
                    'images': formatted_images
                }
            else:
                return {
                    'success': True,
                    'images': []
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== SYSTEM OPERATIONS ====================

    def get_system_info(self):
        """GET /api/system/info - System information"""
        try:
            info = get_system_info()
            free_bytes = check_disk_space(config.TEMP_DIR)

            # Add device information from config
            info['device_name'] = config.JETHOME_DEVICE_NAME
            info['platform'] = config.JETHOME_PLATFORM
            info['emmc_device'] = config.EMMC_DEVICE

            # Get eMMC size
            emmc_size = get_device_size(config.EMMC_DEVICE)
            if emmc_size:
                info['emmc_size'] = emmc_size
                info['emmc_size_human'] = format_bytes(emmc_size)
            else:
                info['emmc_size'] = 0
                info['emmc_size_human'] = 'Unknown'

            # Format disk space
            disk_space = {
                'free': free_bytes,
                'free_human': self._format_bytes(free_bytes)
            }

            return {
                'success': True,
                'info': info,
                'disk_space': disk_space
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _format_bytes(self, bytes):
        """Format bytes to human readable"""
        if bytes == 0:
            return '0 B'
        k = 1024
        sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        i = int(bytes) if bytes > 0 else 0
        i = min(len(sizes) - 1, max(0, int(bytes).bit_length() // 10))
        return f"{round(bytes / (k ** i), 2)} {sizes[i]}"

    def post_system_reboot(self):
        """POST /api/system/reboot - Reboot system"""
        try:
            import subprocess

            # Schedule reboot in 5 seconds (give time for response)
            def reboot_delayed():
                time.sleep(5)
                subprocess.run(['reboot'], check=False)

            thread = threading.Thread(target=reboot_delayed, daemon=True)
            thread.start()

            return {
                'success': True,
                'message': 'System will reboot in 5 seconds'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

