"""
Image flashing module for writing to eMMC
"""

import os
import sys
import subprocess
import tempfile
import time
import lzma
from typing import Optional
import config
from image_writer import validate_range, write_image_stream
from image_cache import cached_image_reader
from translations import t
from utils import (
    print_error, print_success, print_info, print_warning,
    format_bytes, check_device_exists, get_device_size,
    run_command, check_command_exists
)


class FlashHandler:
    """Handle flashing images to eMMC"""

    def __init__(self, emmc_device: str = None):
        self.emmc_device = emmc_device or config.EMMC_DEVICE

    def _protected_range_bytes(self) -> tuple:
        """Validate the recovery window; missing settings must never disable it."""
        start = config.RECOVERY_PROTECT_START_MB
        end = config.RECOVERY_PROTECT_END_MB
        validate_range(start, end, config.DD_BLOCK_SIZE)
        return start * 1024 * 1024, end * 1024 * 1024

    def _writer_command(self) -> list:
        """Use the same protected writer for every external pv/xz pipeline."""
        start, end = self._protected_range_bytes()
        return [
            sys.executable,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image_writer.py'),
            '--target', self.emmc_device,
            '--protect-start', str(start),
            '--protect-end', str(end),
            '--block-size', str(config.DD_BLOCK_SIZE * 1024 * 1024),
        ]

    def verify_emmc_device(self) -> bool:
        """Verify eMMC device exists and is accessible"""
        if not check_device_exists(self.emmc_device):
            print_error(f"eMMC device not found: {self.emmc_device}")
            print_info("Please check config.EMMC_DEVICE setting")
            print_info("Run 'lsblk' to see available devices")
            return False

        size = get_device_size(self.emmc_device)
        if size:
            print_info(f"eMMC device: {self.emmc_device} ({format_bytes(size)})")
        else:
            print_warning(f"eMMC device found but cannot determine size")

        return True

    def check_device_mounted(self) -> list:
        """Check if any partitions on eMMC device are mounted"""
        mounted_partitions = []

        try:
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        device = parts[0]
                        mount_point = parts[1]

                        # Check if device starts with our eMMC device path
                        if device.startswith(self.emmc_device):
                            mounted_partitions.append({
                                'device': device,
                                'mount_point': mount_point
                            })
        except Exception as e:
            print_error(f"Error checking mounts: {e}")

        return mounted_partitions

    def unmount_partitions(self, skip_confirmation: bool = False) -> bool:
        """Check for mounted partitions and handle accordingly

        Args:
            skip_confirmation: Skip console confirmations (for OLED/GUI apps)
        """
        mounted = self.check_device_mounted()

        if not mounted:
            print_success("No mounted partitions - safe to proceed")
            return True

        print_warning(f"Found {len(mounted)} mounted partition(s)")

        # Check for critical mount points (root filesystem)
        critical_mounts = ['/', '/boot', '/usr', '/var', '/etc']
        has_critical = False

        for partition in mounted:
            mount_point = partition['mount_point']
            if mount_point in critical_mounts:
                print_error(f"CRITICAL: {partition['device']} is mounted as {mount_point}")
                has_critical = True

        if has_critical:
            print()

            # Check if mount check is skipped (for testing)
            if config.SKIP_MOUNT_CHECK:
                print_warning("⚠️  SKIP_MOUNT_CHECK is enabled in config.py")
                print_warning("⚠️  This is DANGEROUS and will corrupt the running system!")
                print_warning("⚠️  Only use this for testing purposes!")
                print()

            # Skip console confirmation for OLED/GUI apps
            if not skip_confirmation:
                # Ask for additional confirmation
                from utils import confirm_action
                if not confirm_action("Type 'I UNDERSTAND THE RISK' to proceed", require_yes=False):
                    print_info("Operation cancelled")
                    return False

                response = input("Confirm by typing 'I UNDERSTAND THE RISK': ").strip()
                if response != "I UNDERSTAND THE RISK":
                    print_error("Confirmation failed")
                    return False

                print()
                print_warning("Proceeding with mount check bypassed...")
                print_warning("System WILL be corrupted!")
                print()
            else:
                print_error("Cannot flash eMMC while a filesystem on it is mounted!")
                print()
                print_info("The recovery system runs from RAM (initramfs), so the")
                print_info("eMMC is normally not mounted here. If a partition is")
                print_info("mounted, unmount it or re-enter recovery (hold the")
                print_info("recovery button and power-cycle), then run this again.")
                return False

        # Try to unmount non-critical partitions
        print_info("Attempting to unmount non-critical partitions...")

        for partition in mounted:
            print_info(f"Unmounting {partition['device']} from {partition['mount_point']}")

            # Sync first
            run_command(['sync'], check=False)
            time.sleep(1)

            returncode, _, stderr = run_command(['umount', partition['device']], check=False)

            if returncode != 0:
                print_warning(f"Could not unmount {partition['device']}: {stderr}")
                print_warning("Continuing anyway - make sure data is synced")

        # Always sync before flashing
        print_info("Syncing all filesystems...")
        run_command(['sync'], check=False)
        time.sleep(2)

        print_success("Ready to flash")
        return True

    def confirm_flash(self, image_path: str) -> bool:
        """Curses confirmation screen for flashing image_path to this device."""
        from utils import show_confirm_screen

        is_compressed = image_path.endswith('.xz')
        image_size = os.path.getsize(image_path)
        compressed_label = f" ({t('compressed')})" if is_compressed else ""
        return show_confirm_screen(
            t("confirm_flash_operation"),
            [
                f"{t('image_to_flash')}:",
                f"  {os.path.basename(image_path)}",
                f"  {t('size')}: {format_bytes(image_size)}{compressed_label}",
                "",
                f"{t('target_device')}:",
                f"  {self.emmc_device}",
                "",
                f"⚠️  {t('all_data_erased', device=self.emmc_device)}",
                f"⚠️  {t('cannot_be_undone')}",
            ],
            yes_label=t("flash"),
            no_label=t("cancel"),
        )

    def flash_image(self, image_path: str, verify: bool = False, skip_confirmation: bool = False,
                    progress_cb=None) -> bool:
        """Keep a cached source alive until the complete protected write finishes."""
        try:
            with cached_image_reader(image_path, config.TEMP_DIR):
                return self._flash_image(image_path, verify, skip_confirmation, progress_cb)
        except (OSError, RuntimeError, ValueError) as exc:
            print_error('Cannot use flash source: {}'.format(exc))
            return False

    def _flash_image(self, image_path: str, verify: bool = False, skip_confirmation: bool = False,
                     progress_cb=None) -> bool:
        """
        Flash image to eMMC device

        Args:
            image_path: Path to image file (.img, .img.xz, or .xz)
            verify: Verify write after flashing (slow)
            skip_confirmation: Skip console confirmation (for OLED/GUI apps)

        Returns:
            True if successful, False otherwise
        """
        # Verify image file exists
        if not os.path.exists(image_path):
            print_error(f"Image file not found: {image_path}")
            return False

        try:
            _, protect_end = self._protected_range_bytes()
        except (AttributeError, TypeError, ValueError) as e:
            print_error(f"Invalid recovery protection settings: {e}")
            return False
        if not image_path.endswith('.xz') and os.path.getsize(image_path) <= protect_end:
            print_error("Image contains no data after the recovery window")
            return False

        # Verify eMMC device
        if not self.verify_emmc_device():
            return False

        # Check if image is compressed
        is_compressed = image_path.endswith('.xz')

        image_size = os.path.getsize(image_path)
        image_filename = os.path.basename(image_path)

        # Require explicit confirmation (skip for OLED/GUI apps)
        if not skip_confirmation:
            if not self.confirm_flash(image_path):
                return False

        # Unmount any mounted partitions
        if not self.unmount_partitions(skip_confirmation=skip_confirmation):
            print_error("Cannot proceed with mounted partitions")
            return False

        print()

        # Final check: verify file is still readable (important for USB devices)
        try:
            with open(image_path, 'rb') as f:
                # Try to read first few bytes to ensure file is accessible
                f.read(1024)
        except IOError as e:
            print_error(f"Cannot read image file: {e}")
            print_error("This may happen if:")
            print_error("  - USB device was disconnected or unmounted")
            print_error("  - File system has errors")
            print_error("  - USB device has hardware issues")
            print()
            print_info("Solutions:")
            print_info("  1. Re-mount USB device and try again")
            print_info("  2. Copy image to local storage first")
            print_info("  3. Check USB device with: dmesg | tail")
            return False

        print_info("Starting flash operation...")
        print_warning("DO NOT INTERRUPT THIS PROCESS!")

        # For USB devices, warn user again
        if image_path.startswith('/mnt/') or image_path.startswith('/media/'):
            print_warning("Flashing from removable media - DO NOT REMOVE DEVICE!")

        print()

        try:
            if is_compressed:
                success = self._flash_compressed(image_path, progress_cb=progress_cb)
            else:
                success = self._flash_uncompressed(image_path, progress_cb=progress_cb)

            if not success:
                return False

            # Sync to ensure all data is written
            print_info("Syncing data to disk...")
            run_command(['sync'], check=False)
            time.sleep(2)

            print()
            print_success("Flash operation completed successfully!")
            print_info(f"Successfully flashed {image_path} to {self.emmc_device}")

            print()
            print_info("It is now safe to reboot the system")
            print_warning("Remove any USB drives before rebooting")

            return True

        except KeyboardInterrupt:
            print("\n")
            print_error("Flash operation interrupted!")
            print_warning("Device may be in an unstable state")
            print_error("Flash operation interrupted by user")
            return False

        except Exception as e:
            print_error(f"Flash operation failed: {e}")
            print_error(f"Flash operation failed: {e}")
            return False

    def _flash_pipeline(self, image_path: str, compressed: bool,
                        progress_cb=None) -> bool:
        """Stream pv/xz output through the shared recovery-preserving writer."""
        processes = []
        name = os.path.basename(image_path)
        use_pv = check_command_exists('pv')
        if progress_cb and not use_pv:
            return self._flash_python(image_path, compressed, progress_cb)

        try:
            writer_cmd = self._writer_command()
            size = os.path.getsize(image_path)
            if progress_cb:
                progress_cb(0, name, self.emmc_device)
            with open(image_path, 'rb') as image, tempfile.TemporaryFile() as errors:
                try:
                    source = image
                    pv_process = None
                    if use_pv:
                        pv_process = subprocess.Popen(
                            ['pv', '-n', '-i', '0.5', '-s', str(size)],
                            stdin=image, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        processes.append(('pv', pv_process))
                        source = pv_process.stdout
                    if compressed:
                        xz_process = subprocess.Popen(
                            ['xz', '-dc'], stdin=source, stdout=subprocess.PIPE,
                            stderr=errors)
                        processes.append(('xz', xz_process))
                        if source is not image:
                            source.close()
                        source = xz_process.stdout

                    writer = subprocess.Popen(
                        writer_cmd, stdin=source, stdout=subprocess.DEVNULL,
                        stderr=errors)
                    processes.append(('Image writer', writer))
                    if source is not image:
                        source.close()

                    if pv_process:
                        for line in pv_process.stderr:
                            try:
                                percent = min(99, max(0, int(line.strip())))
                            except ValueError:
                                continue
                            if progress_cb:
                                progress_cb(percent, name, self.emmc_device)
                            elif not getattr(config, 'SILENT_CONSOLE', False):
                                print(f"\rFlashing: {percent}%", end='', flush=True)

                    # Do not report success if a reader or decompressor failed,
                    # even when the writer received EOF and finished cleanly.
                    results = [(label, process.wait()) for label, process in reversed(processes)]
                    failed = [(label, code) for label, code in results if code != 0]
                    if failed:
                        errors.seek(0)
                        detail = errors.read().decode('utf-8', errors='replace').strip()
                        for label, code in failed:
                            print_error(f"{label} failed with code {code}")
                        if detail:
                            print_error(detail)
                        return False
                finally:
                    # A callback error or failed spawn must not leave an orphan
                    # writer running after the frontend reports failure.
                    for _, process in reversed(processes):
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                        for pipe in (process.stdout, process.stderr):
                            if pipe is not None:
                                pipe.close()

            if progress_cb:
                progress_cb(100, name, self.emmc_device)
            elif use_pv and not getattr(config, 'SILENT_CONSOLE', False):
                print()
            return True
        except Exception as e:
            print_error(f"Flash failed: {e}")
            return False

    def _flash_python(self, image_path: str, compressed: bool,
                      progress_cb=None) -> bool:
        """Use bounded-memory Python IO when pv or xz is unavailable."""
        name = os.path.basename(image_path)
        try:
            protect_start, protect_end = self._protected_range_bytes()
            size = os.path.getsize(image_path)
            last_update = time.monotonic()
            if progress_cb:
                progress_cb(0, name, self.emmc_device)

            with open(image_path, 'rb') as image:
                source = lzma.LZMAFile(image, 'rb') if compressed else image
                try:
                    def report(consumed, written):
                        """Keep callbacks responsive without flooding the UI."""
                        nonlocal last_update
                        now = time.monotonic()
                        if now - last_update < 0.5:
                            return
                        percent = min(99, image.tell() * 100 / size) if size else 0
                        status = f"Written: {format_bytes(written)}"
                        if progress_cb:
                            progress_cb(percent, name, status)
                        elif not getattr(config, 'SILENT_CONSOLE', False):
                            print(f"\rFlashing: {percent:.0f}% | {status}",
                                  end='', flush=True)
                        last_update = now

                    written = write_image_stream(
                        source, self.emmc_device, protect_start, protect_end,
                        config.DD_BLOCK_SIZE * 1024 * 1024, progress_cb=report)
                finally:
                    if source is not image:
                        source.close()

            if progress_cb:
                progress_cb(100, name, self.emmc_device)
            elif not getattr(config, 'SILENT_CONSOLE', False):
                print()
            print_success(f"Total written: {format_bytes(written)}")
            return True
        except Exception as e:
            print_error(f"Flash failed: {e}")
            return False

    def _flash_compressed(self, image_path: str, progress_cb=None) -> bool:
        """Decompress on the fly, preserving only the recovery window."""
        if check_command_exists('xz'):
            return self._flash_pipeline(image_path, compressed=True,
                                        progress_cb=progress_cb)
        return self._flash_compressed_python(image_path, progress_cb=progress_cb)

    def _flash_compressed_python(self, image_path: str, progress_cb=None) -> bool:
        """Use Python lzma with the same protected writer as the xz pipeline."""
        return self._flash_python(image_path, compressed=True, progress_cb=progress_cb)

    def _flash_uncompressed(self, image_path: str, progress_cb=None) -> bool:
        """Write an uncompressed disk image around the recovery window."""
        return self._flash_pipeline(image_path, compressed=False, progress_cb=progress_cb)


def select_target_device() -> Optional[str]:
    """
    Interactive function to select target eMMC/SD device using arrow keys

    Returns:
        Device path (e.g., '/dev/mmcblk1') or None
    """
    from utils import find_mmcblk_devices, show_menu, show_text_screen

    devices = find_mmcblk_devices()

    if not devices:
        show_text_screen("Select Target Device", [
            "No mmcblk devices found.",
            "Please check that eMMC/SD devices are connected",
            "(run 'lsblk' to see available devices).",
        ])
        return None

    # Build menu options
    options = []

    # Add "Back/Cancel" option at the top
    options.append("← Back / Cancel")

    for device in devices:
        default_marker = " [DEFAULT]" if device['device'] == config.EMMC_DEVICE else ""
        size_str = format_bytes(device['size'])
        type_str = device['type']
        option = f"{device['device']}{default_marker} - {size_str} - {type_str}"
        options.append(option)

    # Show interactive menu
    choice = show_menu("Select Target Device", options)

    if choice == 0 or choice == 1:
        # Cancelled or "Back" selected
        return None
    elif 2 <= choice <= len(devices) + 1:
        # Selected a device (adjusted for "Back" option)
        return devices[choice - 2]['device']
    else:
        return None


