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
    ensure_directory, is_mounted,
    show_menu
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

def list_usb_devices_interactive() -> Optional[dict]:
    """Discover USB sources in a worker and choose one in an adaptive table."""
    from translations import t
    from utils import show_wait_screen, show_text_screen, show_table_menu
    handler = USBHandler()
    devices, output = show_wait_screen('USB', t('tui_wait'), handler.detect_usb_devices)
    if isinstance(devices, Exception) or not devices:
        show_text_screen('USB', [t('tui_no_usb')])
        return None
    if len(devices) == 1:
        return devices[0]
    rows = [(device['device'], device.get('size', '--'),
             (device.get('vendor', '')+' '+device.get('model', '')).strip())
            for device in devices]
    choice = show_table_menu('USB', [t('tui_target'), t('tui_size'), t('tui_model')], rows)
    return devices[choice-1] if 1 <= choice <= len(devices) else None
