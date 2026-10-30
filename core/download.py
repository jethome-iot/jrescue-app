"""
HTTP download module with progress tracking
"""

import os
import time
import json
import urllib.request
import urllib.error
import urllib.parse
import ssl
from typing import Optional, List
import config
from image_cache import cache_lock, clear_images_unlocked, discard_image, image_identity
from utils import (
    ensure_directory, print_error, print_success, print_info, print_warning,
    format_bytes, format_speed, format_time, show_menu, show_horizontal_menu
)


class DownloadHandler:
    """Handle HTTP downloads with progress tracking"""

    def __init__(self):
        self.last_error = ""
        self.temp_dir = config.TEMP_DIR
        self._completed = {}
        ensure_directory(self.temp_dir)

    def clear_cache(self):
        """Free stale RAM images before the console's free-space check."""
        with cache_lock(self.temp_dir):
            clear_images_unlocked(self.temp_dir)
            self._completed.clear()

    def discard_download(self, path):
        """Discard this handler's completed image once, without deleting a replacement."""
        expected = self._completed.get(path)
        if expected is None:
            return True
        try:
            discard_image(path, self.temp_dir, expected)
            self._completed.pop(path, None)
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            self.last_error = str(exc)
            print_warning('Cannot release downloaded image: {}'.format(exc))
            return False

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
        self.last_error = ""
        try:
            # Under OLED, config is the frontend module inheriting core settings.
            # Keep resolution inside the error boundary so a broken installation
            # produces an API error rather than crashing the whole UI.
            device_id = config.JETHOME_DEVICE
            device_name = config.JETHOME_DEVICE_NAME
            api_url = f"{config.JETHOME_API_BASE}/api/devices/{device_id}/info"
            print_info(f"Fetching firmware list for {device_name}...")
            context = self._create_ssl_context()
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', 'RescueConsole/1.0')
            with urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT,
                                        context=context) as response:
                data = json.loads(response.read().decode('utf-8'))

            firmware_types = data.get('latest_firmware')
            if not isinstance(firmware_types, dict):
                raise ValueError("Invalid API response: missing 'latest_firmware'")
            api_platform = data.get('platform', '')
            expected = config.JETHOME_PLATFORM
            if expected and api_platform and api_platform != expected:
                raise ValueError(f"API platform '{api_platform}' does not match '{expected}'")

            images = []
            for fw_type, fw_data in firmware_types.items():
                # Only SDCard is a raw disk image. Burn containers and RAUC
                # bundles are separate API entries and cannot go to this writer.
                sdcard = fw_data.get('images', {}).get('sdcard')
                if not sdcard or not sdcard.get('url'):
                    continue
                url = urllib.parse.urljoin(config.JETHOME_API_BASE + '/', sdcard['url'])
                filename = os.path.basename(urllib.parse.urlsplit(url).path)
                if (not filename.lower().endswith(('.img', '.img.xz')) or
                        '.burn.' in filename.lower()):
                    continue
                size = int(sdcard.get('filesize') or 0)
                version = str(fw_data['version'])
                date = fw_data.get('date') or 'unknown'
                images.append({
                    'name': f"{fw_type} v{version}",
                    'filename': filename,
                    'url': url,
                    'size': size,
                    'size_mb': size // (1024 * 1024),
                    'version': version,
                    'date': date,
                    'fw_type': fw_type,
                    'description': f"Version {version} ({date[:10]})",
                })

            images.sort(key=lambda im: im['date'] if im['date'] != 'unknown' else '',
                        reverse=True)
            print_success(f"Found {len(images)} firmware images")
            return images
        except Exception as exc:
            self.last_error = str(exc)
            print_error(f"JetHome API: {self.last_error}")
            return None

    def download_file(self, filename_or_url: str, dest_dir: str = None, resume: bool = True,
                      dest_filename: str = None, progress_cb=None, cancel_event=None) -> Optional[str]:
        """Start RAM downloads fresh, clearing old images before opening the URL.

        Explicit destinations outside the RAM cache retain the generic HTTP
        resume behaviour. All application frontends use the managed cache.
        """
        directory = dest_dir if dest_dir is not None else self.temp_dir
        if os.path.realpath(directory) != os.path.realpath(self.temp_dir):
            return self._download_file(filename_or_url, directory, resume,
                                       dest_filename, progress_cb, cancel_event)
        self.last_error = ''
        try:
            parsed = urllib.parse.urlsplit(filename_or_url)
            name = dest_filename if dest_filename is not None else os.path.basename(parsed.path)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise ValueError('Expected a full image URL')
            if (not name or name in ('.', '..') or name != os.path.basename(name) or
                    not name.lower().endswith(('.img', '.xz'))):
                raise ValueError('Invalid image filename')
            with cache_lock(directory):
                clear_images_unlocked(directory)
                self._completed.clear()
                try:
                    result = self._download_file(filename_or_url, directory, False,
                                                  name, progress_cb, cancel_event)
                    if result:
                        self._completed[result] = image_identity(result)
                    return result
                finally:
                    # Failed/interrupted downloads must not leave RAM occupied.
                    partial = os.path.join(directory, name+'.partial')
                    try:
                        os.unlink(partial)
                    except FileNotFoundError:
                        pass
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            self.last_error = str(exc)
            print_error('Download failed: {}'.format(exc))
            return None

    def _download_file(self, filename_or_url: str, dest_dir: str = None, resume: bool = True,
                       dest_filename: str = None, progress_cb=None, cancel_event=None) -> Optional[str]:
        """
        Download a file from the server with progress tracking

        Args:
            filename_or_url: Filename to download or full URL
            dest_dir: Destination directory (default: config.TEMP_DIR)
            resume: Allow resuming interrupted downloads
            dest_filename: Override destination filename
            progress_cb: Optional callable(percent_or_None, *status_lines);
                         when given, progress goes to it instead of stdout
            cancel_event: Optional threading.Event; only downloads support cancel.
                          The caller must wait for this method to close its files.

        Returns:
            Path to downloaded file or None if failed
        """
        self.last_error = ""
        if dest_dir is None:
            dest_dir = self.temp_dir

        ensure_directory(dest_dir)

        # Images always come from the JetHome API as full URLs.
        if not (filename_or_url.startswith('http://') or filename_or_url.startswith('https://')):
            self.last_error = f"Expected a full image URL, got: {filename_or_url}"
            print_error(self.last_error)
            return None
        url = filename_or_url
        if dest_filename is None:
            dest_filename = os.path.basename(url.split('?')[0])

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

        response = None
        try:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError('Download cancelled')
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

            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError('Download cancelled')

            status = response.getcode()
            if start_byte and status == 200:
                # A server may ignore Range. Restart instead of appending a
                # second full image to the existing prefix and accepting it.
                start_byte = 0
            if status == 206:
                content_range = response.headers.get('Content-Range', '')
                expected_prefix = f'bytes {start_byte}-'
                if not content_range.startswith(expected_prefix):
                    response.close()
                    raise ValueError("Server returned an unexpected download range")

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
                # HTTPResponse.read1 returns available bytes instead of waiting
                # to fill a whole megabyte before checking for cancellation.
                read = getattr(response, 'read1', response.read) if cancel_event is not None else response.read

                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError('Download cancelled')
                    chunk = read(chunk_size)
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError('Download cancelled')
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

                            # Calculate ETA
                            eta_str = ""
                            if total_size and speed > 0:
                                remaining_bytes = total_size - downloaded
                                eta_seconds = int(remaining_bytes / speed)
                                eta_str = f"ETA: {format_time(eta_seconds)}"

                            if progress_cb:
                                if total_size:
                                    progress_cb(
                                        downloaded * 100 / total_size,
                                        f"{format_bytes(downloaded)} / {format_bytes(total_size)}",
                                        f"{format_speed(speed)}  {eta_str}".strip()
                                    )
                                else:
                                    progress_cb(None, f"{format_bytes(downloaded)}",
                                                format_speed(speed))
                            elif total_size:
                                percent = (downloaded * 100) // total_size

                                # Visual progress bar (50 chars wide)
                                bar_width = 50
                                filled = int(bar_width * downloaded // total_size)
                                bar = '█' * filled + '░' * (bar_width - filled)

                                sep_eta = f" | {eta_str}" if eta_str else ""
                                print(f"\r[{bar}] {percent}% | {format_bytes(downloaded)}/{format_bytes(total_size)} | {format_speed(speed)}{sep_eta}", end='', flush=True)
                            else:
                                # No total size - show only downloaded and speed
                                print(f"\rDownloading: {format_bytes(downloaded)} | {format_speed(speed)}", end='', flush=True)

                        last_update = current_time

            print()  # New line after progress

            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError('Download cancelled')

            # Verify download completed
            if total_size and os.path.getsize(temp_path) != total_size:
                self.last_error = f"Download incomplete: {os.path.getsize(temp_path)} / {total_size} bytes"
                print_error(self.last_error)
                return None

            # Move temp file to final destination
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(temp_path, dest_path)

            print_success(f"Download complete: {dest_path}")
            print_info(f"Downloaded {dest_filename}")
            return dest_path

        except InterruptedError:
            self.last_error = 'Download cancelled'
            print_warning(self.last_error)
            return None

        except urllib.error.HTTPError as e:
            self.last_error = str(e)
            print_error(f"HTTP Error {e.code}: {e.reason}")
            print_error(f"Download failed: HTTP {e.code} - {e.reason}")
            return None

        except urllib.error.URLError as e:
            self.last_error = str(e)
            print_error(f"Network error: {e.reason}")
            print_error(f"Download failed: {e.reason}")
            return None

        except KeyboardInterrupt:
            self.last_error = "Download interrupted"
            print("\n")
            print_warning("Download interrupted")
            if os.path.abspath(dest_dir) != os.path.abspath(self.temp_dir):
                print_info("Partial file saved, can be resumed later")
            return None

        except Exception as e:
            self.last_error = str(e)
            print_error(f"Download failed: {e}")
            print_error(f"Download failed: {e}")
            return None
        finally:
            if response is not None:
                response.close()

    def _get_remote_file_size(self, url: str) -> Optional[int]:
        """Get remote file size without downloading"""
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT) as response:
                if 'Content-Length' in response.headers:
                    return int(response.headers['Content-Length'])
        except Exception:
            pass

        return None

    def list_available_images(self) -> list:
        """Get the list of available images from the JetHome API."""
        return self.fetch_jethome_images() or []


def select_image_interactive(handler: DownloadHandler) -> Optional[dict]:
    """
    Interactive (curses-only) image selection.

    Returns:
        Selected image dict or None
    """
    from utils import show_wait_screen, show_text_screen

    images, _ = show_wait_screen("Download", "Fetching image list...",
                                 handler.list_available_images)
    if isinstance(images, Exception) or not images:
        show_text_screen("Download", [
            "No images available.",
            "Failed to fetch the image list from the JetHome API.",
            "Check the network connection and try again.",
        ])
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

    choice = show_menu(f"Select Image to Download ({len(images)})", menu_options)

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


def download_image_interactive(handler=None) -> Optional[str]:
    """
    Interactive (curses-only) image download.

    Returns:
        Path to downloaded file or None
    """
    from utils import show_progress_screen, show_text_screen
    import threading

    handler = handler if handler is not None else DownloadHandler()

    # Select image
    image = select_image_interactive(handler)
    if not image:
        return None

    size_str = format_bytes(image['size']) if image.get('size') else "unknown size"
    confirm_choice = show_horizontal_menu(
        f"Download {image['filename']} ({size_str})?",
        ["Cancel", "Download"]
    )

    if confirm_choice != 2:
        return None

    # Download from the JetHome API (always a full URL)
    cancel = threading.Event()
    downloaded = None

    def worker(progress):
        nonlocal downloaded
        progress(None, image['filename'])
        downloaded = handler.download_file(image['url'], dest_filename=image['filename'],
                                           progress_cb=progress, cancel_event=cancel)
        return downloaded

    try:
        result, output = show_progress_screen("Downloading", worker, cancel_event=cancel)
    finally:
        if cancel.is_set() and downloaded:
            handler.discard_download(downloaded)
    if cancel.is_set():
        return None

    if isinstance(result, Exception) or not result:
        tail = [ln for ln in output.strip().splitlines() if ln.strip()][-6:]
        show_text_screen("Download failed", tail or ["Download failed."])
        return None
    return result

