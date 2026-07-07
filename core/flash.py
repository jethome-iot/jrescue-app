"""
Image flashing module for writing to eMMC
"""

import os
import sys
import subprocess
import time
import lzma
from typing import Optional
import config
from translations import t
from utils import (
    print_error, print_success, print_info, print_warning,
    format_bytes, format_time, check_device_exists, get_device_size,
    run_command
)


class FlashHandler:
    """Handle flashing images to eMMC"""

    def __init__(self, emmc_device: str = None):
        self.emmc_device = emmc_device or config.EMMC_DEVICE

    def _protect_offset_bytes(self) -> int:
        """Bytes at the start of the target that must NOT be written.

        See config.RECOVERY_PROTECT_MB — this covers the bootloader, its env and
        both recovery slots, which are writable from inside recovery and would be
        destroyed by a whole-disk dd from sector 0.
        """
        return max(0, int(getattr(config, 'RECOVERY_PROTECT_MB', 0))) * 1024 * 1024

    def _dd_offset_args(self) -> list:
        """dd operands that skip the protected region on both input and output.

        Byte-exact (iflag=skip_bytes / oflag=seek_bytes), so it does not depend on
        the offset being a multiple of the dd block size. iflag=fullblock makes the
        skip exact when the input is a pipe (xz/pv). Empty when nothing is protected.
        """
        off = self._protect_offset_bytes()
        if off <= 0:
            return []
        return [
            'iflag=fullblock,skip_bytes',
            'oflag=seek_bytes',
            f'skip={off}',
            f'seek={off}',
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

    def flash_image(self, image_path: str, verify: bool = False, skip_confirmation: bool = False) -> bool:
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

        # Verify eMMC device
        if not self.verify_emmc_device():
            return False

        # Check if image is compressed
        is_compressed = image_path.endswith('.xz')

        image_size = os.path.getsize(image_path)
        image_filename = os.path.basename(image_path)

        # Require explicit confirmation (skip for OLED/GUI apps)
        if not skip_confirmation:
            # Show detailed confirmation with horizontal menu
            from utils import show_horizontal_menu

            print()
            # Format confirmation message
            size_label = t("size")
            compressed_label = f" ({t('compressed')})" if is_compressed else ""
            size_info = f"  {size_label}: {format_bytes(image_size)}{compressed_label}"
            image_label = t("image_to_flash")
            target_label = t("target_device")
            warning_label = "⚠️  WARNING:"
            erased_msg = t("all_data_erased", device=self.emmc_device)
            cannot_undo = t("cannot_be_undone")
            title = t("confirm_flash_operation")

            confirmation_text = f"""╔═══════════════════════════════════════════════╗
║     {title:<41} ║
╠═══════════════════════════════════════════════╣
║                                               ║
║ {image_label}:                               ║
║   {image_filename:<43} ║
║ {size_info:<45} ║
║                                               ║
║ {target_label}:                                ║
║   {self.emmc_device:<43} ║
║                                               ║
║ {warning_label:<45} ║
║   {erased_msg:<43} ║
║   {cannot_undo:<43} ║
║                                               ║
╚═══════════════════════════════════════════════╝"""
            print(confirmation_text)

            choice = show_horizontal_menu(
                t("proceed_with_flashing"),
                [t("cancel"), t("flash")]
            )

            if choice != 2:  # Not "Flash" (Flash is option 2)
                print_info(t("download_cancelled"))
                return False

        print()

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
                success = self._flash_compressed(image_path)
            else:
                success = self._flash_uncompressed(image_path)

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

    def _flash_compressed(self, image_path: str) -> bool:
        """Flash compressed (.xz) image using decompression on the fly"""
        print_info("Decompressing and flashing (this will take several minutes)...")
        print_info("Using STREAMING decompression - image is NOT loaded into RAM")
        print()

        # Use xz command if available for better performance
        from utils import check_command_exists

        # Get compressed file size for progress calculation
        compressed_size = os.path.getsize(image_path)

        if check_command_exists('xz'):
            # Check if pv is available for better progress
            use_pv = check_command_exists('pv')

            if use_pv:
                print_info("Using xz + pv for streaming decompression with progress")
                print()

                # Build command: pv -f image.xz | xz -dc | dd of=/dev/mmcblk0 bs=4M
                # -f forces pv to output progress even when stderr is not a terminal
                pv_cmd = ['pv', '-f', '-pterb', '-s', str(compressed_size), image_path]
                xz_cmd = ['xz', '-dc']
                dd_cmd = [
                    'dd',
                    f'of={self.emmc_device}',
                    f'bs={config.DD_BLOCK_SIZE}M',
                    'conv=fsync',
                    'status=none'  # Silence dd, let pv show progress
                ] + self._dd_offset_args()

                try:
                    # Start pv process (reads compressed file) with unbuffered output
                    pv_env = os.environ.copy()
                    pv_env['PYTHONUNBUFFERED'] = '1'

                    # For OLED: redirect pv output to /dev/null
                    pv_stderr = subprocess.DEVNULL if getattr(config, 'SILENT_CONSOLE', False) else subprocess.PIPE

                    pv_process = subprocess.Popen(
                        pv_cmd,
                        stdout=subprocess.PIPE,
                        stderr=pv_stderr,  # Keep stderr separate or redirect to null
                        env=pv_env,
                        bufsize=0
                    )

                    # Start xz process (decompresses)
                    xz_process = subprocess.Popen(
                        xz_cmd,
                        stdin=pv_process.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL
                    )
                    pv_process.stdout.close()  # Allow pv to receive SIGPIPE

                    # Start dd process (writes to device)
                    dd_process = subprocess.Popen(
                        dd_cmd,
                        stdin=xz_process.stdout,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    xz_process.stdout.close()

                    # Read pv progress from stderr in real-time (unless silent mode)
                    if not getattr(config, 'SILENT_CONSOLE', False):
                        import fcntl
                        # Set stderr to non-blocking mode
                        fd = pv_process.stderr.fileno()
                        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                        while True:
                            try:
                                # Read available data
                                chunk = pv_process.stderr.read(4096)
                                if chunk:
                                    sys.stdout.write(chunk.decode('utf-8', errors='replace'))
                                    sys.stdout.flush()
                            except (IOError, OSError):
                                # No data available yet
                                pass

                            # Check if process finished
                            if dd_process.poll() is not None:
                                # Read any remaining output
                                try:
                                    remaining = pv_process.stderr.read()
                                    if remaining:
                                        sys.stdout.write(remaining.decode('utf-8', errors='replace'))
                                        sys.stdout.flush()
                                except:
                                    pass
                                break

                            time.sleep(0.1)
                    else:
                        # Silent mode: just wait for process to finish
                        dd_process.wait()

                    if not getattr(config, 'SILENT_CONSOLE', False):
                        print()  # New line after progress

                    # Wait for all processes to complete
                    dd_returncode = dd_process.wait()
                    xz_returncode = xz_process.wait()
                    pv_returncode = pv_process.wait()

                    if dd_returncode != 0:
                        print_error(f"dd command failed with code {dd_returncode}")
                        return False

                    if xz_returncode != 0:
                        print_error(f"xz command failed with code {xz_returncode}")
                        return False

                    return True

                except Exception as e:
                    print_error(f"Flash failed: {e}")
                    return False

            else:
                # Use xz with dd status=progress
                print_info("Using xz command for streaming decompression")
                print()

                # Build command: xz -dc image.xz | dd of=/dev/mmcblk0 bs=4M status=progress
                xz_cmd = ['xz', '-dc', image_path]
                dd_cmd = [
                    'dd',
                    f'of={self.emmc_device}',
                    f'bs={config.DD_BLOCK_SIZE}M',
                    'conv=fsync'
                ] + self._dd_offset_args()

                # Check if dd supports status=progress
                returncode, _, _ = run_command(['dd', '--help'], check=False)
                dd_help_result = run_command(['dd', '--help'], check=False)
                if 'status=progress' in str(dd_help_result):
                    dd_cmd.append('status=progress')

                try:
                    # Start xz process
                    xz_process = subprocess.Popen(
                        xz_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )

                    # Start dd process
                    dd_process = subprocess.Popen(
                        dd_cmd,
                        stdin=xz_process.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )

                    # Allow xz_process to receive SIGPIPE if dd_process exits
                    xz_process.stdout.close()

                    # Read output
                    for line in dd_process.stdout:
                        print(line, end='', flush=True)

                    # Wait for processes to complete
                    dd_returncode = dd_process.wait()
                    xz_returncode = xz_process.wait()

                    if dd_returncode != 0:
                        print_error(f"dd command failed with code {dd_returncode}")
                        return False

                    if xz_returncode != 0:
                        print_error(f"xz command failed with code {xz_returncode}")
                        return False

                    return True

                except Exception as e:
                    print_error(f"Flash failed: {e}")
                    return False

        else:
            # Fallback to Python lzma module
            print_info("Using Python lzma module for decompression")
            return self._flash_compressed_python(image_path)

    def _flash_compressed_python(self, image_path: str) -> bool:
        """Flash compressed image using Python's lzma module"""
        print()
        print_info("Progress indicator:")
        print()

        try:
            # Get compressed size for progress estimation
            compressed_size = os.path.getsize(image_path)

            with lzma.open(image_path, 'rb') as src:
                with open(self.emmc_device, 'wb') as dst:
                    # Use larger buffer for better performance
                    buffer_size = config.DD_BLOCK_SIZE * 1024 * 1024  # DD_BLOCK_SIZE in MB
                    bytes_written = 0
                    bytes_read_compressed = 0
                    start_time = time.time()
                    last_update = start_time

                    # Get underlying file object for tracking compressed bytes
                    compressed_fp = src._fp if hasattr(src, '_fp') else None

                    # Preserve the protected recovery region (see _dd_offset_args):
                    # discard the image's first RECOVERY_PROTECT_MB of decompressed
                    # data and write the rest at that offset. dst is a block device,
                    # so seeking past [0, offset) leaves that region untouched.
                    protect_offset = self._protect_offset_bytes()
                    if protect_offset > 0:
                        remaining = protect_offset
                        while remaining > 0:
                            skip_chunk = src.read(min(buffer_size, remaining))
                            if not skip_chunk:
                                print_error("Image smaller than protected region — aborting")
                                return False
                            remaining -= len(skip_chunk)
                        dst.seek(protect_offset)

                    while True:
                        chunk = src.read(buffer_size)
                        if not chunk:
                            break

                        dst.write(chunk)
                        bytes_written += len(chunk)

                        # Track compressed bytes read (if possible)
                        if compressed_fp and hasattr(compressed_fp, 'tell'):
                            try:
                                bytes_read_compressed = compressed_fp.tell()
                            except:
                                pass

                        # Update progress every second
                        current_time = time.time()
                        if current_time - last_update >= 0.5:
                            elapsed = current_time - start_time
                            if elapsed > 0:
                                speed = bytes_written / elapsed

                                # Calculate progress percentage based on compressed bytes
                                progress_parts = [f"Written: {format_bytes(bytes_written)}"]

                                if bytes_read_compressed > 0 and compressed_size > 0:
                                    percent = min(100, (bytes_read_compressed * 100) // compressed_size)
                                    progress_parts.append(f"({percent}%)")

                                    # Calculate ETA
                                    if percent > 0 and percent < 100:
                                        total_time_estimate = elapsed * 100 / percent
                                        eta = int(total_time_estimate - elapsed)
                                        progress_parts.append(f"ETA: {format_time(eta)}")

                                progress_parts.append(f"Speed: {format_bytes(speed)}/s")

                                # Draw simple progress bar
                                bar_width = 30
                                if bytes_read_compressed > 0 and compressed_size > 0:
                                    filled = int(bar_width * bytes_read_compressed / compressed_size)
                                    bar = "█" * filled + "░" * (bar_width - filled)
                                    print(f"\r[{bar}] {' | '.join(progress_parts)}", end='', flush=True)
                                else:
                                    print(f"\r{' | '.join(progress_parts)}", end='', flush=True)

                            last_update = current_time

                    print()  # New line
                    print()
                    print_success(f"Total written: {format_bytes(bytes_written)}")

            return True

        except Exception as e:
            print()
            print_error(f"Flash failed: {e}")
            return False

    def _flash_uncompressed(self, image_path: str) -> bool:
        """Flash uncompressed image using dd"""
        print_info("Flashing image (this will take several minutes)...")
        print()

        # Check if pv is available
        from utils import check_command_exists
        use_pv = check_command_exists('pv')

        if use_pv:
            # Use pv for progress display
            image_size = os.path.getsize(image_path)
            print_info("Using pv for progress display")
            print()

            # Build command: pv -f image.img | dd of=/dev/mmcblk0 bs=4M
            # -f forces pv to output progress even when stderr is not a terminal
            pv_cmd = ['pv', '-f', '-pterb', '-s', str(image_size), image_path]
            dd_cmd = [
                'dd',
                f'of={self.emmc_device}',
                f'bs={config.DD_BLOCK_SIZE}M',
                'conv=fsync',
                'status=none'  # Silence dd
            ] + self._dd_offset_args()

            try:
                # Start pv process with unbuffered stderr
                pv_env = os.environ.copy()
                pv_env['PYTHONUNBUFFERED'] = '1'

                # For OLED: redirect pv output to /dev/null
                pv_stderr = subprocess.DEVNULL if getattr(config, 'SILENT_CONSOLE', False) else subprocess.PIPE

                pv_process = subprocess.Popen(
                    pv_cmd,
                    stdout=subprocess.PIPE,
                    stderr=pv_stderr,  # Keep stderr separate or redirect to null
                    env=pv_env,
                    bufsize=0  # Unbuffered
                )

                # Start dd process
                dd_process = subprocess.Popen(
                    dd_cmd,
                    stdin=pv_process.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                pv_process.stdout.close()  # Allow pv to receive SIGPIPE

                # Read pv progress from stderr in real-time (unless silent mode)
                if not getattr(config, 'SILENT_CONSOLE', False):
                    import fcntl
                    # Set stderr to non-blocking mode
                    fd = pv_process.stderr.fileno()
                    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                    while True:
                        try:
                            # Read available data
                            chunk = pv_process.stderr.read(4096)
                            if chunk:
                                sys.stdout.write(chunk.decode('utf-8', errors='replace'))
                                sys.stdout.flush()
                        except (IOError, OSError):
                            # No data available yet
                            pass

                        # Check if process finished
                        if dd_process.poll() is not None:
                            # Read any remaining output
                            try:
                                remaining = pv_process.stderr.read()
                                if remaining:
                                    sys.stdout.write(remaining.decode('utf-8', errors='replace'))
                                    sys.stdout.flush()
                            except:
                                pass
                            break

                        time.sleep(0.1)

                    print()  # New line after progress
                else:
                    # Silent mode: just wait for process to finish
                    dd_process.wait()

                # Wait for processes
                dd_returncode = dd_process.wait()
                pv_returncode = pv_process.wait()

                if dd_returncode != 0:
                    print_error(f"Flash failed: dd returned {dd_returncode}")
                    return False

                return True

            except Exception as e:
                print_error(f"Flash failed: {e}")
                return False

        else:
            # Use dd with status=progress
            # Build dd command
            dd_cmd = [
                'dd',
                f'if={image_path}',
                f'of={self.emmc_device}',
                f'bs={config.DD_BLOCK_SIZE}M',
                'conv=fsync'
            ] + self._dd_offset_args()

            # Check if dd supports status=progress
            returncode, stdout, _ = run_command(['dd', '--help'], check=False)
            if 'status=progress' in stdout:
                dd_cmd.append('status=progress')

            # Run dd command (output goes to terminal)
            returncode, _, stderr = run_command(dd_cmd, check=False, capture=False)

            if returncode != 0:
                print_error(f"Flash failed: {stderr}")
                return False

            return True


def select_target_device() -> Optional[str]:
    """
    Interactive function to select target eMMC/SD device using arrow keys

    Returns:
        Device path (e.g., '/dev/mmcblk1') or None
    """
    from utils import find_mmcblk_devices, show_menu

    devices = find_mmcblk_devices()

    if not devices:
        print_error("No mmcblk devices found")
        print_info("Please check that eMMC/SD devices are connected")
        print_info("Run 'lsblk' to see available devices")
        return config.EMMC_DEVICE  # Fallback to config default

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


