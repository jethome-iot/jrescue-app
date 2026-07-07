"""
HTTP download module with progress tracking
"""

import os
import time
import json
import urllib.request
import urllib.error
import ssl
from typing import Optional, List
import config
from utils import (
    ensure_directory, print_error, print_success, print_info, print_warning,
    format_bytes, format_speed, format_time, show_menu, show_horizontal_menu, clear_screen
)


class DownloadHandler:
    """Handle HTTP downloads with progress tracking"""

    def __init__(self, server_url: str = None):
        self.server_url = server_url or config.DEFAULT_SERVER
        self.temp_dir = config.TEMP_DIR
        self.use_jethome_api = config.JETHOME_API_ENABLED
        ensure_directory(self.temp_dir)

    def _create_ssl_context(self):
        """Create SSL context for HTTPS requests"""
        context = ssl.create_default_context()
        # For self-signed certificates or testing, you might need:
        # context.check_hostname = False
        # context.verify_mode = ssl.CERT_NONE
        return context

    def fetch_jethome_images(self) -> Optional[List[dict]]:
        """
        Fetch available images from JetHome API

        Returns:
            List of image dicts or None if failed
        """
        if not self.use_jethome_api:
            return None

        # Use current device from config
        device_id = config.JETHOME_DEVICE
        device_name = config.JETHOME_DEVICE_NAME

        api_url = f"{config.JETHOME_API_BASE}/api/devices/{device_id}/info"

        print_info(f"Fetching firmware list for {device_name}...")
        print_info(f"API URL: {api_url} (device: {device_id})")

        try:
            context = self._create_ssl_context()
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', 'RescueConsole/1.0')

            with urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT, context=context) as response:
                data = json.loads(response.read().decode('utf-8'))

            if 'latest_firmware' not in data:
                print_error("Invalid API response: missing 'latest_firmware'")
                return None

            images = []
            firmware_types = data['latest_firmware']

            # Filter firmware types if configured
            if config.JETHOME_FIRMWARE_FILTER:
                firmware_types = {k: v for k, v in firmware_types.items()
                                 if k in config.JETHOME_FIRMWARE_FILTER}

            for fw_type, fw_data in firmware_types.items():
                # Only process if sdcard image exists
                if 'images' not in fw_data or 'sdcard' not in fw_data['images']:
                    continue

                sdcard = fw_data['images']['sdcard']

                # Create image entry
                image = {
                    'name': f"{fw_type} v{fw_data['version']}",
                    'filename': os.path.basename(sdcard['url']),
                    'url': f"{config.JETHOME_API_BASE}{sdcard['url']}",
                    'size': sdcard.get('filesize', 0),
                    'size_mb': sdcard.get('filesize', 0) // (1024 * 1024),
                    'version': fw_data['version'],
                    'date': fw_data.get('date', 'unknown'),
                    'fw_type': fw_type,
                    'description': f"Version {fw_data['version']} ({fw_data.get('date', 'unknown')[:10]})"
                }

                images.append(image)

            if images:
                print_success(f"Found {len(images)} firmware images")
                print_info(f"Fetched {len(images)} images from JetHome API")
            else:
                print_warning("No images found in API response")

            return images

        except urllib.error.HTTPError as e:
            print_error(f"HTTP Error {e.code}: {e.reason}")
            print_error(f"JetHome API HTTP error: {e.code} - {e.reason}")
            return None

        except urllib.error.URLError as e:
            print_error(f"Network error: {e.reason}")
            print_error(f"JetHome API network error: {e.reason}")
            return None

        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON response: {e}")
            print_error(f"JetHome API JSON error: {e}")
            return None

        except Exception as e:
            print_error(f"Failed to fetch images: {e}")
            print_error(f"JetHome API error: {e}")
            return None

    def download_file(self, filename_or_url: str, dest_dir: str = None, resume: bool = True, dest_filename: str = None) -> Optional[str]:
        """
        Download a file from the server with progress tracking

        Args:
            filename_or_url: Filename to download or full URL
            dest_dir: Destination directory (default: config.TEMP_DIR)
            resume: Allow resuming interrupted downloads
            dest_filename: Override destination filename

        Returns:
            Path to downloaded file or None if failed
        """
        if dest_dir is None:
            dest_dir = self.temp_dir

        ensure_directory(dest_dir)

        # Check if it's a full URL or just a filename
        if filename_or_url.startswith('http://') or filename_or_url.startswith('https://'):
            url = filename_or_url
            if dest_filename is None:
                dest_filename = os.path.basename(url.split('?')[0])
        else:
            url = f"{self.server_url}/{filename_or_url}"
            dest_filename = dest_filename or filename_or_url

        dest_path = os.path.join(dest_dir, dest_filename)
        temp_path = dest_path + ".partial"

        # Check if file already exists and is complete
        if os.path.exists(dest_path) and not os.path.exists(temp_path):
            print_info(f"File {dest_filename} already exists")

            # Verify size if possible
            try:
                local_size = os.path.getsize(dest_path)
                remote_size = self._get_remote_file_size(url)

                if remote_size and local_size == remote_size:
                    print_success("File is complete, skipping download")
                    return dest_path
                else:
                    print_warning("File size mismatch, re-downloading...")
                    os.remove(dest_path)
            except Exception:
                pass

        # Check for partial download
        start_byte = 0
        if resume and os.path.exists(temp_path):
            start_byte = os.path.getsize(temp_path)
            print_info(f"Resuming download from {format_bytes(start_byte)}")

        print_info(f"Downloading: {dest_filename}")
        print_info(f"URL: {url}")

        try:
            # Create request with resume support
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'RescueConsole/1.0')
            if start_byte > 0:
                req.add_header('Range', f'bytes={start_byte}-')

            # Create SSL context for HTTPS
            context = self._create_ssl_context() if url.startswith('https://') else None

            # Add timeout
            if context:
                response = urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT, context=context)
            else:
                response = urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT)

            # Get file size
            total_size = None
            if 'Content-Length' in response.headers:
                content_length = int(response.headers['Content-Length'])
                total_size = start_byte + content_length
            elif 'Content-Range' in response.headers:
                # Parse Content-Range: bytes start-end/total
                content_range = response.headers['Content-Range']
                if '/' in content_range:
                    total_size = int(content_range.split('/')[-1])

            if total_size:
                print_info(f"Total size: {format_bytes(total_size)}")

            # Open file for writing
            mode = 'ab' if start_byte > 0 else 'wb'

            with open(temp_path, mode) as f:
                downloaded = start_byte
                start_time = time.time()
                last_update = start_time
                chunk_size = config.DOWNLOAD_CHUNK_SIZE

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress every 0.5 seconds
                    current_time = time.time()
                    if current_time - last_update >= 0.5:
                        elapsed = current_time - start_time

                        if elapsed > 0:
                            speed = (downloaded - start_byte) / elapsed

                            # Build progress display
                            if total_size:
                                percent = (downloaded * 100) // total_size

                                # Visual progress bar (50 chars wide)
                                bar_width = 50
                                filled = int(bar_width * downloaded // total_size)
                                bar = '█' * filled + '░' * (bar_width - filled)

                                # Calculate ETA
                                eta_str = ""
                                if speed > 0:
                                    remaining_bytes = total_size - downloaded
                                    eta_seconds = int(remaining_bytes / speed)
                                    eta_str = f" | ETA: {format_time(eta_seconds)}"

                                # Print progress with bar
                                print(f"\r[{bar}] {percent}% | {format_bytes(downloaded)}/{format_bytes(total_size)} | {format_speed(speed)}{eta_str}", end='', flush=True)
                            else:
                                # No total size - show only downloaded and speed
                                print(f"\rDownloading: {format_bytes(downloaded)} | {format_speed(speed)}", end='', flush=True)

                        last_update = current_time

            print()  # New line after progress

            # Verify download completed
            if total_size and os.path.getsize(temp_path) != total_size:
                print_error(f"Download incomplete: {os.path.getsize(temp_path)} / {total_size} bytes")
                return None

            # Move temp file to final destination
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(temp_path, dest_path)

            print_success(f"Download complete: {dest_path}")
            print_info(f"Downloaded {dest_filename}")
            return dest_path

        except urllib.error.HTTPError as e:
            print_error(f"HTTP Error {e.code}: {e.reason}")
            print_error(f"Download failed: HTTP {e.code} - {e.reason}")
            return None

        except urllib.error.URLError as e:
            print_error(f"Network error: {e.reason}")
            print_error(f"Download failed: {e.reason}")
            return None

        except KeyboardInterrupt:
            print("\n")
            print_warning("Download interrupted")
            print_info("Partial file saved, can be resumed later")
            return None

        except Exception as e:
            print_error(f"Download failed: {e}")
            print_error(f"Download failed: {e}")
            return None

    def _get_remote_file_size(self, url: str) -> Optional[int]:
        """Get remote file size without downloading"""
        try:
            req = urllib.request.Request(url, method='HEAD')
            response = urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT)

            if 'Content-Length' in response.headers:
                return int(response.headers['Content-Length'])
        except Exception:
            pass

        return None

    def test_server_connection(self) -> bool:
        """Test if server is reachable"""
        print_info(f"Testing connection to {self.server_url}...")

        try:
            req = urllib.request.Request(self.server_url, method='HEAD')
            response = urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT)

            print_success("Server is reachable")
            return True

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # 404 means server responded, just no index page
                print_success("Server is reachable")
                return True
            else:
                print_error(f"Server error: HTTP {e.code}")
                return False

        except urllib.error.URLError as e:
            print_error(f"Cannot reach server: {e.reason}")
            return False

        except Exception as e:
            print_error(f"Connection test failed: {e}")
            return False

    def list_available_images(self) -> list:
        """
        Get list of available images from configuration or JetHome API

        Returns:
            List of image dicts
        """
        # Try JetHome API first if enabled
        if self.use_jethome_api:
            images = self.fetch_jethome_images()
            if images:
                return images
            else:
                print_warning("Failed to fetch from JetHome API, using static config")

        return config.AVAILABLE_IMAGES


def select_image_interactive(handler: DownloadHandler) -> Optional[dict]:
    """
    Interactive function to select an image to download
    Uses arrow keys navigation (like Midnight Commander)

    Returns:
        Selected image dict or None
    """
    images = handler.list_available_images()

    if not images:
        clear_screen()
        print_error("No images available")
        if handler.use_jethome_api:
            print_info("Failed to fetch from JetHome API and no static images configured")
        else:
            print_info("Please add images to config.AVAILABLE_IMAGES")
        return None

    # Build menu options
    menu_options = []

    # Add "Back/Cancel" option at the top (like ".." in file managers)
    menu_options.append("← Back / Cancel")

    # Add each image as a formatted menu option
    for image in images:
        # Format: "Name | Size | Version"
        name = image['name']

        # Handle size display
        if 'size' in image and image['size'] > 0:
            size_str = format_bytes(image['size'])
        elif 'size_mb' in image:
            size_str = f"~{image['size_mb']} MB"
        else:
            size_str = "Unknown size"

        # Format the menu line
        menu_line = f"{name} | {size_str}"
        menu_options.append(menu_line)

    # Show interactive menu
    print_info(f"Found {len(images)} firmware image(s)")
    print_info("Use ↑↓ arrow keys to navigate, Enter to select")
    print()

    choice = show_menu("Select Image to Download", menu_options)

    # choice == 0 means cancelled or error
    # choice == 1 means "Back/Cancel" was selected
    if choice == 0 or choice == 1:
        return None

    # choice >= 2 means an image was selected
    # Subtract 2 because: 1 for 1-based indexing, 1 for "Back" option
    image_index = choice - 2
    if 0 <= image_index < len(images):
        return images[image_index]

    return None


def download_image_interactive() -> Optional[str]:
    """
    Interactive function to download an image

    Returns:
        Path to downloaded file or None
    """
    handler = DownloadHandler()

    # Test server connection only if NOT using JetHome API
    if not handler.use_jethome_api:
        if not handler.test_server_connection():
            print_error("Cannot connect to server")
            print_info(f"Current server: {handler.server_url}")
            print_info(f"You can change it in config.py: DEFAULT_SERVER")
            return None

    # Select image
    image = select_image_interactive(handler)
    if not image:
        return None

    print()
    print_info(f"Selected: {image['name']}")
    print_info(f"Filename: {image['filename']}")

    # Show size if available
    if 'size' in image and image['size'] > 0:
        from utils import format_bytes
        print_info(f"Size: {format_bytes(image['size'])}")

    print()

    # Confirm download with horizontal interactive menu
    confirm_choice = show_horizontal_menu(
        "Proceed with download?",
        ["Cancel", "Download"]
    )

    if confirm_choice != 2:
        print_info("Download cancelled")
        return None

    print()

    # Download - check if we have a full URL or just filename
    if 'url' in image:
        # Full URL (e.g., from JetHome API)
        return handler.download_file(image['url'], dest_filename=image['filename'])
    else:
        # Just filename (from static config)
        return handler.download_file(image['filename'])

