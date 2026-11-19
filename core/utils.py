"""
Utility functions for Rescue Console Application
"""

import os
import sys
import subprocess
import shutil
import time
import socket
from typing import Tuple, Optional, List
import config

# Try to import curses for interactive menu
try:
    # Esc responds in 25ms instead of the ~1s ncurses default (must be set
    # before the first initscr).
    os.environ.setdefault('ESCDELAY', '25')
    import curses
    CURSES_AVAILABLE = True
except ImportError:
    CURSES_AVAILABLE = False


def check_root() -> bool:
    """Check if running as root"""
    return os.geteuid() == 0


def require_root():
    """Exit if not running as root"""
    if not check_root():
        print_error("This application requires root privileges!")
        print_info("Please run with: sudo python3 main.py")
        sys.exit(1)


def clear_screen():
    """Clear terminal screen"""
    os.system('clear')


def print_header(text: str):
    """Print a formatted header"""
    width = 75
    print("\n" + "=" * width)
    print(text.center(width))
    print("=" * width + "\n")


def print_box(text: str):
    """Print text in a box (respects VERBOSE_LOGS)"""
    if getattr(config, 'SILENT_CONSOLE', False):
        return
    if not getattr(config, 'VERBOSE_LOGS', True):
        return

    lines = text.split('\n')
    max_len = max(len(line) for line in lines)
    width = max_len + 4

    print("+" + "-" * (width - 2) + "+")
    for line in lines:
        padding = max_len - len(line)
        print("| " + line + " " * padding + " |")
    print("+" + "-" * (width - 2) + "+")


def print_success(message: str):
    """Print success message (respects VERBOSE_LOGS)"""
    if not getattr(config, 'SILENT_CONSOLE', False):
        if getattr(config, 'VERBOSE_LOGS', True):
            print(f"[OK] {message}")


def print_error(message: str):
    """Print error message (always shown unless SILENT_CONSOLE)"""
    if not getattr(config, 'SILENT_CONSOLE', False):
        print(f"[ERROR] {message}")


def print_warning(message: str):
    """Print warning message (always shown unless SILENT_CONSOLE)"""
    if not getattr(config, 'SILENT_CONSOLE', False):
        print(f"[WARNING] {message}")


def print_info(message: str):
    """Print info message (respects VERBOSE_LOGS)"""
    if not getattr(config, 'SILENT_CONSOLE', False):
        if getattr(config, 'VERBOSE_LOGS', True):
            print(f"[INFO] {message}")


def format_bytes(bytes_size: int) -> str:
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def format_speed(bytes_per_second: float) -> str:
    """Format download speed"""
    return f"{format_bytes(bytes_per_second)}/s"


def format_time(seconds: int) -> str:
    """Format seconds to human readable time"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def run_command(cmd: List[str], check: bool = True, capture: bool = True,
                timeout: Optional[float] = None) -> Tuple[int, str, str]:
    """
    Run a shell command and return (returncode, stdout, stderr)

    Args:
        cmd: Command as list of strings
        check: Raise exception on non-zero return code
        capture: Capture output (if False, output goes to terminal)
        timeout: seconds before the child is killed, returning (-1, "", "timed out").
            Without it a wedged helper (e.g. nmcli stalled on D-Bus) blocks the
            caller forever — in the provisioning path that means the setup-AP is
            never brought back and the device becomes unreachable.

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    try:
        if capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, check=check, timeout=timeout)
            return result.returncode, "", ""
    except subprocess.TimeoutExpired:
        return -1, "", "timed out"
    except subprocess.CalledProcessError as e:
        if capture:
            return e.returncode, e.stdout if e.stdout else "", e.stderr if e.stderr else ""
        else:
            return e.returncode, "", ""
    except Exception as e:
        print_error(f"Command execution failed: {e}")
        return -1, "", str(e)


def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH"""
    return shutil.which(command) is not None


def check_disk_space(path: str = "/tmp") -> int:
    """Check available disk space in bytes"""
    stat = shutil.disk_usage(path)
    return stat.free


def ensure_directory(path: str):
    """Ensure directory exists, create if not"""
    os.makedirs(path, exist_ok=True)


def check_device_exists(device: str) -> bool:
    """Check if a block device exists"""
    return os.path.exists(device)


def get_device_size(device: str) -> Optional[int]:
    """Get device size in bytes"""
    try:
        with open(f"/sys/class/block/{os.path.basename(device)}/size", 'r') as f:
            # Size is in 512-byte sectors
            sectors = int(f.read().strip())
            return sectors * 512
    except Exception:
        return None


def confirm_action(prompt: str, require_yes: bool = False, max_attempts: int = 5) -> bool:
    """Keep legacy core confirmations inside curses with a safe default."""
    from translations import t
    if require_yes:
        return show_action_confirmation(t('warning'), [prompt], 'CONFIRM')
    return show_confirm_screen(t('confirm_title'), [prompt], t('yes'), t('no'))


def wait_with_spinner(seconds: int, message: str = "Please wait"):
    """Show a spinner while waiting"""
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    end_time = time.time() + seconds
    idx = 0

    while time.time() < end_time:
        remaining = int(end_time - time.time())
        print(f"\r{spinner[idx % len(spinner)]} {message}... ({remaining}s)", end='', flush=True)
        time.sleep(0.1)
        idx += 1

    print("\r" + " " * 80 + "\r", end='', flush=True)  # Clear line

def _init_colors():
    """Initialize the approved Classic palette."""
    import tui
    tui.init_colors()


def _run_curses(callback, *args, **kwargs):
    """Reuse the active console session; standalone callers still get a wrapper."""
    import tui
    return tui.run(callback, *args, **kwargs)


def run_console_ui(callback):
    """Run the frontend inside one curses lifetime."""
    import tui
    return tui.session(callback)


def _draw_frame(stdscr, title, hint=''):
    """Paint an adaptive Classic dialog and return its body geometry."""
    import tui
    while True:
        frame = tui.new_frame(stdscr, title, hint)
        if frame.paint(stdscr, refresh=False):
            break
    stdscr.attrset(tui.attribute('body'))
    return frame.y, frame.x, frame.height, frame.width


def show_menu_interactive_curses(stdscr, title, options, title_fn=None,
                                 refresh_ms=2000, main=False, initial_index=0):
    """Draw an arrow-key menu using the shared Classic renderer."""
    import tui
    return tui.menu(stdscr, title, options, title_fn, refresh_ms, main, initial_index)


def show_menu(title, options, title_fn=None, refresh_ms=2000, main=False, initial_index=0):
    """Return a one-based selection; zero cancels without an action."""
    return _run_curses(show_menu_interactive_curses, title, options, title_fn,
                       refresh_ms, main, initial_index)


def show_menu_horizontal_curses(stdscr, title, options):
    """Draw an explicit horizontal choice with the first option selected."""
    import tui
    return tui.horizontal_menu(stdscr, title, options)


def show_horizontal_menu(title, options):
    """Return the selected button number, or zero on cancellation."""
    return _run_curses(show_menu_horizontal_curses, title, options)


def input_dialog_curses(stdscr, title, prompt, password=False, initial='', background=None):
    """Support insertion, deletion and masked password display."""
    import tui
    return tui.input_dialog(stdscr, title, prompt, password, initial, background)


def input_dialog(title, prompt, password=False, initial='', background=None):
    """Cancel safely on any input or display failure."""
    try:
        return _run_curses(input_dialog_curses, title, prompt, password, initial, background)
    except Exception:
        return None


def show_text_screen_curses(stdscr, title, lines, refresh_fn=None, refresh_ms=2000):
    """Show wrapped, scrollable text without plain terminal output."""
    import tui
    return tui.text_screen(stdscr, title, lines, refresh_fn, refresh_ms)


def show_text_screen(title, lines, refresh_fn=None, refresh_ms=2000):
    """Keep passive reports inside curses, including their error paths."""
    return _run_curses(show_text_screen_curses, title, lines, refresh_fn, refresh_ms)


def show_table_menu(title, columns, rows, details=None):
    """Choose a table row, retaining complete details beneath the selection."""
    import tui
    return _run_curses(tui.table_menu, title, columns, rows, details)


def show_network_screen(devices, **kwargs):
    """Return a requested action; reading status never changes a connection."""
    import tui
    return _run_curses(tui.network_screen, devices, **kwargs)


def show_power_pending(title):
    """Show an accepted shutdown request without returning to actionable menus."""
    import tui
    return _run_curses(tui.power_pending, title)


def show_action_confirmation(title, lines, token):
    """Only an exact token and explicit Enter can start a critical action."""
    import tui
    try:
        return _run_curses(tui.action_confirmation, title, lines, token) is True
    except Exception:
        return False


def show_compact_confirmation(title, lines, size=(64, 11)):
    """Only an explicit OK with the full warning visible approves an action."""
    import tui
    try:
        return _run_curses(tui.compact_confirmation, title, lines, size) is True
    except Exception:
        return False


def show_confirm_screen(title, lines, yes_label='YES', no_label='NO'):
    """Select Cancel by default; failures never count as approval."""
    import tui
    try:
        return _run_curses(tui.horizontal_menu, title, [no_label, yes_label], lines) == 2
    except Exception:
        return False


def show_settings_screen_curses(stdscr, title, items):
    """Keep the declarative runtime-settings API for existing callers."""
    import tui
    return tui.settings(stdscr, title, items)


def show_settings_screen(title, items):
    """Show runtime-only settings in Classic dialogs."""
    return _run_curses(show_settings_screen_curses, title, items)


def _run_operation(title, worker, cancel_event=None, message=''):
    """Join one worker even after terminal failure; never retry an active write."""
    import contextlib
    import io
    import threading
    import tui
    done = threading.Event()
    lock = threading.Lock()
    state = {'percent': None, 'lines': (message,) if message else (), 'result': None}
    output = io.StringIO()

    def report(percent, *lines):
        with lock:
            state['percent'], state['lines'] = percent, tuple(map(str, lines))

    def runner():
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                state['result'] = worker(report)
        except Exception as exc:
            state['result'] = exc
        finally:
            done.set()

    def ui(stdscr):
        _init_colors()
        stdscr.nodelay(True)
        frame = 0
        while not done.is_set():
            pressed = stdscr.getch()
            if cancel_event is not None and pressed == 27:
                cancel_event.set()
            with lock:
                percent, lines = state['percent'], state['lines']
            cancelling = cancel_event is not None and cancel_event.is_set()
            heading = tui.t('download_cancelling') if cancelling else title
            hint = tui.t('hint_download_cancel') if cancel_event is not None else tui.t('tui_write_busy') if percent is not None else tui.t('tui_wait')
            y, x, height, width = _draw_frame(stdscr, heading, hint)
            content_width = min(width, tui.content_width(lines, 60))
            x += (width - content_width) // 2
            width = content_width
            row = y + max(0, height // 2 - 2)
            if percent is None or cancelling:
                text = '|/-\\'[frame % 4]+' ' + tui.t('tui_wait')
            else:
                value = min(100, max(0, percent))
                bar_width = max(1, width - 9)
                filled = round(bar_width * value / 100)
                text = '[' + '#' * filled + '-' * (bar_width - filled)+'] ' + str(round(value)).rjust(3)+'%'
            if height:
                stdscr.addstr(row, x, tui.fit(text, width), tui.attribute('accent'))
            row += 2
            for line in lines:
                for part in tui.wrap(line, width):
                    if row < y + height:
                        stdscr.addstr(row, x, part)
                    row += 1
            stdscr.refresh()
            frame += 1
            curses.napms(80)

    thread = threading.Thread(target=runner)
    thread.start()
    try:
        _run_curses(ui)
    except Exception:
        if cancel_event is not None:
            cancel_event.set()
    except BaseException:
        if cancel_event is not None:
            cancel_event.set()
        raise
    finally:
        thread.join()
        try:
            curses.flushinp()
        except curses.error:
            pass
    return state['result'], output.getvalue()


def show_wait_screen(title, message, fn, *args, **kwargs):
    """Run one bounded operation and animate it only on the UI thread."""
    return _run_operation(title, lambda progress:fn(*args, **kwargs), message=message)


def show_progress_screen(title, worker, cancel_event=None):
    """Only downloads get a cancel token; all workers finish before returning."""
    return _run_operation(title, worker, cancel_event=cancel_event)


def press_enter_to_continue():
    """Wait for user to press Enter"""
    try:
        input("\nPress Enter to continue...")
    except KeyboardInterrupt:
        print()


def get_system_info() -> dict:
    """Get system information"""
    info = {}

    # Hostname
    try:
        info['hostname'] = subprocess.check_output(['hostname'], text=True).strip()
    except Exception:
        info['hostname'] = "unknown"

    # Kernel
    try:
        info['kernel'] = subprocess.check_output(['uname', '-r'], text=True).strip()
    except Exception:
        info['kernel'] = "unknown"

    # Architecture
    try:
        info['arch'] = subprocess.check_output(['uname', '-m'], text=True).strip()
    except Exception:
        info['arch'] = "unknown"

    # Memory
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    mem_kb = int(line.split()[1])
                    info['memory'] = format_bytes(mem_kb * 1024)
                    break
    except Exception:
        info['memory'] = "unknown"

    # Disk space
    info['disk_free'] = format_bytes(check_disk_space())

    return info


def is_mounted(mount_point: str) -> bool:
    """Check if a path is a mount point"""
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == mount_point:
                    return True
        return False
    except Exception:
        return False


def get_mmc_device_type(device_name: str) -> str:
    """
    Determine MMC device type by reading from sysfs

    Args:
        device_name: Device name without /dev/ (e.g., 'mmcblk0')

    Returns:
        Device type string: 'SD', 'MMC', 'SDIO', or 'Unknown'
    """
    try:
        type_path = f"/sys/block/{device_name}/device/type"
        if os.path.exists(type_path):
            with open(type_path, 'r') as f:
                device_type = f.read().strip()
                return device_type
    except Exception as e:
        print_error(f"Could not read device type for {device_name}: {e}")

    return "Unknown"


def find_mmcblk_devices() -> list:
    """
    Find all available mmcblk devices (eMMC/SD cards)
    Excludes boot partitions (mmcblkXbootY) and rpmb devices
    Uses sysfs to accurately determine device type (SD vs eMMC)

    Returns:
        List of dicts with device info: {'device': '/dev/mmcblk0', 'size': bytes, 'model': str}
    """
    devices = []

    try:
        import json
        import re

        # Use lsblk to get block devices in JSON format
        result = subprocess.run(
            ['lsblk', '-J', '-b', '-o', 'NAME,SIZE,TYPE,MODEL,HOTPLUG'],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print_error(f"lsblk failed: {result.stderr}")
            return devices

        data = json.loads(result.stdout)

        for device in data.get('blockdevices', []):
            name = device.get('name', '')

            # Only include mmcblk devices (eMMC and SD cards)
            # Exclude boot partitions (mmcblk0boot0, mmcblk0boot1, etc.)
            # Exclude rpmb devices (mmcblk0rpmb)
            # Pattern: mmcblk followed by only digits (e.g., mmcblk0, mmcblk1)
            if re.match(r'^mmcblk\d+$', name) and device.get('type') == 'disk':
                size = device.get('size', 0)
                model = device.get('model', 'Unknown')
                hotplug = device.get('hotplug', False)

                # Get accurate device type from sysfs
                sysfs_type = get_mmc_device_type(name)

                # Determine device type with priority:
                # 1. sysfs type (most accurate)
                # 2. hotplug flag (fallback)
                if sysfs_type == "SD":
                    device_type = "SD Card"
                    is_removable = True
                elif sysfs_type == "MMC":
                    device_type = "eMMC"
                    is_removable = False
                elif sysfs_type == "SDIO":
                    device_type = "SDIO"
                    is_removable = hotplug
                else:
                    # Fallback to hotplug detection
                    if hotplug:
                        device_type = "SD Card (detected by hotplug)"
                        is_removable = True
                    else:
                        device_type = "eMMC (detected by hotplug)"
                        is_removable = False

                # Build description
                if is_removable:
                    type_description = f"{device_type} (removable)"
                else:
                    type_description = f"{device_type} (internal)"

                devices.append({
                    'device': f"/dev/{name}",
                    'size': int(size) if size else 0,
                    'model': model if model else device_type,
                    'hotplug': hotplug,
                    'type': type_description,
                    'sysfs_type': sysfs_type,
                    'is_removable': is_removable
                })

        # Sort devices by name
        devices.sort(key=lambda x: x['device'])

    except json.JSONDecodeError as e:
        print_error(f"Failed to parse lsblk JSON: {e}")
    except Exception as e:
        print_error(f"Error finding mmcblk devices: {e}")

    return devices


def check_web_app_status(host: str = "localhost", port: int = 8124) -> bool:
    """
    Check if web application is running on specified host and port

    Args:
        host: Host to check (default: localhost)
        port: Port to check (default: 8124)

    Returns:
        True if web app is accessible, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)  # 1 second timeout
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_local_ip() -> Optional[str]:
    """
    Get local IP address for web interface access
    Priority: eth0 > wlan0 > default route

    Returns:
        Local IP address string or None if not found
    """
    import subprocess

    # Try eth0 first (highest priority)
    try:
        result = subprocess.run(['ip', 'addr', 'show', 'eth0'],
                              capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and not '127.' in line:
                    ip = line.split('inet ')[1].split('/')[0].strip()
                    if ip:
                        return ip
    except Exception:
        pass

    # Try wlan0 second
    try:
        result = subprocess.run(['ip', 'addr', 'show', 'wlan0'],
                              capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and not '127.' in line:
                    ip = line.split('inet ')[1].split('/')[0].strip()
                    if ip:
                        return ip
    except Exception:
        pass

    # Fallback: use default route method (original behavior)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # Doesn't actually connect, just determines local IP
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            return ip
        except Exception:
            pass
        finally:
            s.close()
    except Exception:
        pass

    return None


def create_clickable_link(url: str, text: str = None) -> str:
    """
    Create a clickable link for terminal using OSC 8 escape sequence

    Args:
        url: URL to link to
        text: Display text (defaults to URL)

    Returns:
        Formatted string with clickable link
    """
    if text is None:
        text = url

    # OSC 8 escape sequence for hyperlinks (supported by modern terminals)
    # Format: \033]8;;URL\033\\TEXT\033]8;;\033\\
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"

