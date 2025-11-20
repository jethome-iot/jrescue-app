"""
USB device detection and mounting module
"""

import os
import json
import time
from typing import List, Optional
import config
from utils import (
    run_command, print_error, print_success, print_info, print_warning,
    ensure_directory, is_mounted, print_info, print_error, wait_with_spinner,
    show_menu, clear_screen
)


class USBHandler:
    """Handle USB device detection and mounting"""

    def __init__(self):
        self.mount_point = config.USB_MOUNT_POINT
        ensure_directory(self.mount_point)

    def detect_usb_devices(self) -> List[dict]:
        """
        Detect USB storage devices mounted at USB_MOUNT_POINT
        Returns list of dicts with device info
        """
        print_info(f"Detecting USB devices mounted at {self.mount_point}...")

        returncode, stdout, stderr = run_command(['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,VENDOR,MODEL'], check=False)

        if returncode != 0:
            print_error(f"Failed to list block devices: {stderr}")
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            print_error(f"Failed to parse lsblk output: {e}")
            return []

        usb_devices = []

        # Look for USB devices mounted at our mount point
        for device in data.get('blockdevices', []):
            # Skip if it's the eMMC device
            device_path = f"/dev/{device['name']}"
            if device_path.startswith(config.EMMC_DEVICE):
                continue

            # Check if it's a disk (not partition)
            if device.get('type') == 'disk':
                # Check if it has partitions
                partitions = device.get('children', [])

                if partitions:
                    # Check partitions for our mount point
                    for part in partitions:
                        if part.get('type') == 'part':
                            mountpoint = part.get('mountpoint')
                            # Only add if mounted at our mount point
                            if mountpoint == self.mount_point:
                                usb_devices.append({
                                    'device': f"/dev/{part['name']}",
                                    'name': part['name'],
                                    'size': part.get('size', 'Unknown'),
                                    'mountpoint': mountpoint,
                                    'vendor': (device.get('vendor') or '').strip(),
                                    'model': (device.get('model') or '').strip()
                                })
                else:
                    # No partitions, check if disk itself is mounted at our mount point
                    mountpoint = device.get('mountpoint')
                    if mountpoint == self.mount_point:
                        usb_devices.append({
                            'device': device_path,
                            'name': device['name'],
                            'size': device.get('size', 'Unknown'),
                            'mountpoint': mountpoint,
                            'vendor': (device.get('vendor') or '').strip(),
                            'model': (device.get('model') or '').strip()
                        })

        return usb_devices

    def wait_for_usb(self, timeout: int = None) -> Optional[List[dict]]:
        """
        Wait for USB device to be mounted at USB_MOUNT_POINT

        Args:
            timeout: Timeout in seconds (None = use config default)

        Returns:
            List of USB devices or None if timeout
        """
        if timeout is None:
            timeout = config.USB_DETECTION_TIMEOUT

        print_info(f"Waiting for USB device at {self.mount_point} (timeout: {timeout}s)...")
        print_info("Please insert a USB drive and mount it")

        start_time = time.time()
        last_check_time = 0

        while time.time() - start_time < timeout:
            # Check every 2 seconds
            if time.time() - last_check_time >= 2:
                devices = self.detect_usb_devices()
                if devices:
                    print_success(f"Found {len(devices)} USB device(s) at {self.mount_point}")
                    return devices
                last_check_time = time.time()

            remaining = int(timeout - (time.time() - start_time))
            print(f"\rWaiting... ({remaining}s remaining)", end='', flush=True)
            time.sleep(0.5)

        print()
        print_warning(f"No USB device found at {self.mount_point}")
        return None

    def mount_device(self, device: str, mount_point: str = None) -> bool:
        """
        Mount a USB device

        Args:
            device: Device path (e.g., /dev/sdb1)
            mount_point: Mount point (default: config.USB_MOUNT_POINT)

        Returns:
            True if successful, False otherwise
        """
        if mount_point is None:
            mount_point = self.mount_point

        # Check if already mounted
        if is_mounted(mount_point):
            print_warning(f"{mount_point} is already mounted")
            # Try to unmount first
            if not self.unmount_device(mount_point):
                return False

        # Ensure mount point exists
        ensure_directory(mount_point)

        print_info(f"Mounting {device} to {mount_point}...")

        # Try mounting with auto-detection of filesystem
        returncode, stdout, stderr = run_command(['mount', device, mount_point], check=False)

        if returncode == 0:
            print_success(f"Mounted {device}")
            print_info(f"Mounted {device} to {mount_point}")
            return True
        else:
            print_error(f"Failed to mount: {stderr}")
            print_error(f"Mount failed: {stderr}")
            return False

    def unmount_device(self, mount_point: str = None) -> bool:
        """
        Unmount a device

        Args:
            mount_point: Mount point to unmount (default: config.USB_MOUNT_POINT)

        Returns:
            True if successful, False otherwise
        """
        if mount_point is None:
            mount_point = self.mount_point

        if not is_mounted(mount_point):
            return True

        print_info(f"Unmounting {mount_point}...")

        # Sync before unmount
        run_command(['sync'], check=False)
        time.sleep(1)

        returncode, _, stderr = run_command(['umount', mount_point], check=False)

        if returncode == 0:
            print_success(f"Unmounted {mount_point}")
            print_info(f"Unmounted {mount_point}")
            return True
        else:
            # Try force unmount
            print_warning("Attempting force unmount...")
            returncode, _, stderr = run_command(['umount', '-f', mount_point], check=False)

            if returncode == 0:
                print_success(f"Force unmounted {mount_point}")
                return True
            else:
                print_error(f"Failed to unmount: {stderr}")
                return False

    def scan_for_images(self, mount_point: str = None) -> List[dict]:
        """
        Scan mounted USB for image files (.xz, .img, .img.xz)

        Args:
            mount_point: Path to scan (default: config.USB_MOUNT_POINT)

        Returns:
            List of dicts with image info
        """
        if mount_point is None:
            mount_point = self.mount_point

        if not os.path.exists(mount_point):
            print_error(f"Mount point {mount_point} does not exist")
            return []

        if not is_mounted(mount_point):
            print_error(f"{mount_point} is not mounted")
            return []

        print_info(f"Scanning {mount_point} for images...")

        images = []
        skipped_files = []

        try:
            # Walk through the directory
            for root, dirs, files in os.walk(mount_point):
                for filename in files:
                    # Check for image files
                    if filename.endswith(('.img.xz', '.xz', '.img')):
                        # Skip .burn images - they are archives, not flashable images
                        if '.burn.' in filename or filename.endswith('.burn.img'):
                            print_info(f"Skipping burn archive: {filename}")
                            skipped_files.append(filename)
                            continue

                        filepath = os.path.join(root, filename)

                        try:
                            size = os.path.getsize(filepath)

                            images.append({
                                'filename': filename,
                                'path': filepath,
                                'size': size,
                                'relative_path': os.path.relpath(filepath, mount_point)
                            })
                        except OSError as e:
                            print_error(f"Error accessing {filepath}: {e}")
                            continue

        except Exception as e:
            print_error(f"Error scanning directory: {e}")
            print_error(f"Directory scan error: {e}")
            return []

        # Inform user about skipped files
        if skipped_files:
            print()
            print_warning("Skipped .burn archives (not suitable for direct flashing):")
            for skipped in skipped_files:
                print_info(f"  - {skipped}")
            print_info("Only sdcard images (.img.xz, .img) can be flashed directly")
            print()

        if images:
            print_success(f"Found {len(images)} image(s)")
        else:
            print_warning("No image files found")

        return images

    def copy_image_from_usb(self, source_path: str, dest_dir: str = None) -> Optional[str]:
        """
        Copy image from USB to destination directory

        NOTE: This function is NOT used in main workflow.
        Images are flashed directly from USB without copying (streaming decompression).
        Kept for backward compatibility or manual use.

        Args:
            source_path: Full path to image on USB
            dest_dir: Destination directory (default: config.TEMP_DIR)

        Returns:
            Path to copied file or None if failed
        """
        if dest_dir is None:
            dest_dir = config.TEMP_DIR

        ensure_directory(dest_dir)

        filename = os.path.basename(source_path)
        dest_path = os.path.join(dest_dir, filename)

        # Check if already exists
        if os.path.exists(dest_path):
            # Check if same size
            try:
                source_size = os.path.getsize(source_path)
                dest_size = os.path.getsize(dest_path)

                if source_size == dest_size:
                    print_info(f"File {filename} already exists with same size, skipping copy")
                    return dest_path
            except OSError:
                pass

        print_info(f"Copying {filename}...")
        print_warning("This may take several minutes depending on file size")

        try:
            # Get source size for progress
            source_size = os.path.getsize(source_path)
        except OSError:
            source_size = 0

        # Use dd for copying with progress (if pv is available) or cp
        if source_size > 0:
            # Try with pv for progress
            from utils import check_command_exists
            if check_command_exists('pv'):
                returncode, _, stderr = run_command(
                    ['pv', source_path],
                    check=False
                )

                if returncode == 0:
                    with open(dest_path, 'wb') as f:
                        run_command(['pv', source_path], check=False, capture=False)

                    returncode = 0
                else:
                    # Fallback to cp
                    returncode, _, stderr = run_command(['cp', source_path, dest_path], check=False, capture=False)
            else:
                # Use cp with verbose
                print_info("Copying... (no progress indicator available)")
                returncode, _, stderr = run_command(['cp', '-v', source_path, dest_path], check=False, capture=False)
        else:
            returncode, _, stderr = run_command(['cp', source_path, dest_path], check=False)

        if returncode == 0:
            print_success(f"Copied to {dest_path}")
            print_info(f"Copied {filename} from USB")
            return dest_path
        else:
            print_error(f"Copy failed: {stderr}")
            print_error(f"Copy failed: {stderr}")
            return None


def list_usb_devices_interactive() -> Optional[dict]:
    """
    Interactive function to list and select USB device
    Uses arrow keys navigation (like Midnight Commander)

    Returns:
        Selected device dict or None
    """
    handler = USBHandler()

    devices = handler.detect_usb_devices()

    if not devices:
        print_warning(f"No USB devices mounted at {handler.mount_point}")
        print_info("Please insert USB drive and ensure it's mounted to /mnt/usb")
        print()
        print_info("No USB device found")
        return None

    if len(devices) == 1:
        device = devices[0]
        vendor_model = f"{device['vendor']} {device['model']}".strip()
        print_info(f"Found: {device['device']} ({device['size']}) {vendor_model}")
        return device
    else:
        # Multiple devices - show interactive menu
        print_info(f"Found {len(devices)} USB device(s)")
        print_info("Use ↑↓ arrow keys to navigate, Enter to select")
        print()

        # Build menu options
        menu_options = []
        menu_options.append("← Back / Cancel")

        for device in devices:
            vendor_model = f"{device['vendor']} {device['model']}".strip()
            mounted = f" [Mounted: {device['mountpoint']}]" if device['mountpoint'] else ""
            menu_line = f"{device['device']} | {device['size']} | {vendor_model}{mounted}"
            menu_options.append(menu_line)

        choice = show_menu("Select USB Device", menu_options)

        # choice == 0 or 1 means cancelled or "Back" selected
        if choice == 0 or choice == 1:
            return None

        # choice >= 2 means a device was selected
        device_index = choice - 2
        if 0 <= device_index < len(devices):
            return devices[device_index]

        return None

