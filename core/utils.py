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


def run_command(cmd: List[str], check: bool = True, capture: bool = True) -> Tuple[int, str, str]:
    """
    Run a shell command and return (returncode, stdout, stderr)

    Args:
        cmd: Command as list of strings
        check: Raise exception on non-zero return code
        capture: Capture output (if False, output goes to terminal)

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    try:
        if capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, check=check)
            return result.returncode, "", ""
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
    """
    Ask user for confirmation using interactive menu

    Args:
        prompt: Question to ask user
        require_yes: If True, show as critical confirmation (ignored, uses menu)
        max_attempts: Maximum number of attempts (default: 5)

    Returns:
        True if confirmed, False otherwise
    """
    # For critical actions, show warning
    if require_yes:
        print()
        print_warning("⚠️  CRITICAL ACTION - PLEASE CONFIRM")

    print_info(prompt)
    print()

    choice = show_menu(
        "Confirm Action",
        ["✓ YES - Proceed with operation", "✗ NO - Cancel operation"]
    )
    return choice == 1


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
    """Initialize the shared color pairs used by every curses screen."""
    if not curses.has_colors():
        return
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)   # selected
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)    # frame/title
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)   # normal text
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # hint
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)    # input field


def _draw_frame(stdscr, title: str, hint: str = "") -> tuple:
    """Draw a full-screen menuconfig-style frame.

    ┌─[ TITLE ]───────────────┐
    │  ...content area...     │
    ├─────────────────────────┤   (only when hint is given)
    │ hint                    │
    └─────────────────────────┘

    Returns (y0, x0, inner_h, inner_w) of the content area.
    """
    h, w = stdscr.getmaxyx()
    if h < 6 or w < 20:  # degrade gracefully on tiny terminals
        return 0, 0, h, w

    frame_attr = (curses.color_pair(2) | curses.A_BOLD) if curses.has_colors() else 0

    label = f"[ {title} ]"
    if len(label) > w - 6:
        label = label[:w - 9] + "… ]"

    try:
        stdscr.attron(frame_attr)
        # top border with embedded title
        top = "┌" + "─" * (w - 2) + "┐"
        stdscr.addstr(0, 0, top[:w - 1])
        try:
            stdscr.addstr(0, w - 1, "┐")
        except curses.error:
            pass
        stdscr.addstr(0, max(1, (w - len(label)) // 2), label)
        # side borders
        bottom_border_y = h - 1
        hint_sep_y = h - 3 if hint else None
        for y in range(1, bottom_border_y):
            stdscr.addstr(y, 0, "│")
            try:
                stdscr.addstr(y, w - 1, "│")
            except curses.error:
                pass
        if hint:
            stdscr.addstr(hint_sep_y, 0, "├" + "─" * (w - 2))
            try:
                stdscr.addstr(hint_sep_y, w - 1, "┤")
            except curses.error:
                pass
        # bottom border
        try:
            stdscr.addstr(bottom_border_y, 0, "└" + "─" * (w - 2) + "┘")
        except curses.error:
            pass  # writing the last cell always raises after drawing
        stdscr.attroff(frame_attr)

        if hint:
            hint_attr = curses.color_pair(4) if curses.has_colors() else 0
            stdscr.attron(hint_attr)
            stdscr.addstr(h - 2, 2, hint[:max(0, w - 4)])
            stdscr.attroff(hint_attr)
    except curses.error:
        pass

    inner_h = (hint_sep_y if hint else bottom_border_y) - 1
    return 1, 2, inner_h, w - 4


def show_menu_interactive_curses(stdscr, title: str, options: List[str]) -> int:
    """
    Interactive menu using curses (arrow keys navigation)

    Args:
        stdscr: Curses screen object
        title: Menu title
        options: List of menu options

    Returns:
        Selected option number (1-based) or 0 if cancelled
    """
    curses.curs_set(0)  # Hide cursor
    _init_colors()

    current_row = 0
    top = 0

    while True:
        stdscr.erase()
        # menuconfig-style: full-screen frame, compact left-aligned list,
        # scrolling for long lists. No syscalls in the draw loop.
        y0, x0, body_h, body_w = _draw_frame(
            stdscr, title, "↑↓ move   Enter select   1-9 jump   Esc back")
        y0 += 1  # breathing row under the top border
        body_h = max(1, body_h - 1)

        if current_row < top:
            top = current_row
        elif current_row >= top + body_h:
            top = current_row - body_h + 1
        top = max(0, min(top, max(0, len(options) - body_h)))

        for i in range(body_h):
            idx = top + i
            if idx >= len(options):
                break
            marker = "❯" if idx == current_row else " "
            line = f" {marker} {idx + 1}. {options[idx]} "
            if len(line) > body_w - 2:
                line = line[:max(0, body_w - 5)] + "..."
            try:
                if idx == current_row:
                    attr = (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() \
                        else curses.A_REVERSE
                    stdscr.addstr(y0 + i, x0 + 1, line, attr)
                elif curses.has_colors():
                    stdscr.addstr(y0 + i, x0 + 1, line, curses.color_pair(3))
                else:
                    stdscr.addstr(y0 + i, x0 + 1, line)
            except curses.error:
                pass

        # Scroll indicator for long lists
        if len(options) > body_h:
            pos = f"[{current_row + 1}/{len(options)}]"
            try:
                stdscr.addstr(0, max(0, stdscr.getmaxyx()[1] - len(pos) - 3), pos)
            except curses.error:
                pass

        stdscr.refresh()

        # Get user input
        key = stdscr.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(options) - 1:
            current_row += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:  # Enter key
            return current_row + 1
        elif key in (27, ord('q'), ord('Q')):  # Esc / q = cancel
            return 0
        elif key >= ord('1') and key <= ord('9'):  # Digit keys 1-9
            digit = key - ord('0')
            # Jump to item by number (1-based)
            if 1 <= digit <= len(options):
                current_row = digit - 1


def show_menu_horizontal_curses(stdscr, title: str, options: List[str]) -> int:
    """
    Horizontal menu using curses (left/right arrow keys navigation)
    Perfect for simple choices like Yes/No, OK/Cancel, etc.

    Args:
        stdscr: Curses screen object
        title: Menu title/question
        options: List of menu options (will be displayed horizontally)

    Returns:
        Selected option number (1-based) or 0 if cancelled
    """
    curses.curs_set(0)  # Hide cursor
    _init_colors()

    current_option = 0

    while True:
        stdscr.erase()
        y0, x0, body_h, body_w = _draw_frame(
            stdscr, "Confirm", "←→ move   Enter select   Esc back")

        # Wrap the question inside the frame
        title_lines = []
        max_title_width = max(10, body_w - 4)
        current_line = ""
        for word in title.split():
            if len(current_line) + len(word) + 1 <= max_title_width:
                current_line += (word + " ")
            else:
                if current_line:
                    title_lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            title_lines.append(current_line.strip())

        w = stdscr.getmaxyx()[1]
        text_y = max(y0 + 1, y0 + (body_h - len(title_lines) - 3) // 2)
        for idx, line in enumerate(title_lines):
            if text_y + idx >= y0 + body_h - 2:
                break
            try:
                stdscr.addstr(text_y + idx, max(x0, (w - len(line)) // 2), line,
                              curses.color_pair(3) if curses.has_colors() else 0)
            except curses.error:
                pass

        # menuconfig-style single-row buttons:  < Cancel >   < Flash >
        buttons = [f"< {opt} >" for opt in options]
        total_width = sum(len(b) for b in buttons) + 4 * (len(buttons) - 1)
        bx = max(x0, (w - total_width) // 2)
        by = min(y0 + body_h - 1, text_y + len(title_lines) + 2)
        for idx, btn in enumerate(buttons):
            try:
                if idx == current_option:
                    attr = (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() \
                        else curses.A_REVERSE
                    stdscr.addstr(by, bx, btn, attr)
                else:
                    stdscr.addstr(by, bx, btn)
            except curses.error:
                pass
            bx += len(btn) + 4

        stdscr.refresh()

        # Get user input
        key = stdscr.getch()

        if key in (curses.KEY_LEFT, curses.KEY_UP) and current_option > 0:
            current_option -= 1
        elif key in (curses.KEY_RIGHT, curses.KEY_DOWN, ord('\t')) and current_option < len(options) - 1:
            current_option += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:  # Enter key
            return current_option + 1
        elif key in (27, ord('q'), ord('Q')):  # Esc / q = cancel
            return 0
        elif key >= ord('1') and key <= ord('9'):  # Digit keys 1-9
            digit = key - ord('0')
            if 1 <= digit <= len(options):
                return digit


def show_menu(title: str, options: List[str]) -> int:
    """
    Display an arrow-key menu (curses) and return the choice.

    Args:
        title: Menu title
        options: List of menu options

    Returns:
        Selected option number (1-based), or 0 if cancelled.
    """
    try:
        return curses.wrapper(show_menu_interactive_curses, title, options)
    except Exception as e:
        print_error(f"Menu error: {e}")
        return 0


def input_dialog_curses(stdscr, title: str, prompt: str, password: bool = False) -> Optional[str]:
    """
    menuconfig-style input dialog: framed prompt, input field, < Cancel > < OK >.

    Focus order: input field -> Cancel -> OK (Tab/arrows cycle).
    Esc cancels. Returns the entered string or None if cancelled.
    """
    curses.curs_set(1)
    _init_colors()

    user_input = ""
    current_focus = 0  # 0 = input field, 1 = Cancel, 2 = OK

    try:
        while True:
            stdscr.erase()
            y0, x0, body_h, body_w = _draw_frame(
                stdscr, title, "Tab/↑↓ focus   Enter select   Esc cancel")
            w = stdscr.getmaxyx()[1]

            # Prompt
            prompt_y = y0 + max(1, (body_h - 6) // 2)
            try:
                stdscr.addstr(prompt_y, max(x0, (w - len(prompt)) // 2), prompt,
                              curses.color_pair(3) if curses.has_colors() else 0)
            except curses.error:
                pass

            # Input field
            input_width = min(40, body_w - 4)
            input_x = max(x0, (w - input_width) // 2)
            input_y = prompt_y + 2
            display_text = user_input
            if len(display_text) > input_width - 4:
                display_text = display_text[-(input_width - 4):]
            field_attr = curses.color_pair(5) if curses.has_colors() else curses.A_UNDERLINE
            if current_focus == 0:
                field_attr |= curses.A_BOLD
            try:
                stdscr.addstr(input_y, input_x,
                              f" {display_text:<{input_width - 2}} ", field_attr)
            except curses.error:
                pass

            # Buttons: < Cancel >   < OK >
            buttons = ["< Cancel >", "< OK >"]
            total = sum(len(b) for b in buttons) + 4
            bx = max(x0, (w - total) // 2)
            by = input_y + 2
            for idx, btn in enumerate(buttons, start=1):
                try:
                    if current_focus == idx:
                        attr = (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() \
                            else curses.A_REVERSE
                        stdscr.addstr(by, bx, btn, attr)
                    else:
                        stdscr.addstr(by, bx, btn)
                except curses.error:
                    pass
                bx += len(btn) + 4

            # Cursor into the field when focused
            if current_focus == 0:
                cursor_x = input_x + 1 + min(len(display_text), input_width - 3)
                try:
                    stdscr.move(input_y, min(cursor_x, w - 2))
                except curses.error:
                    pass

            stdscr.refresh()
            key = stdscr.getch()

            if key == 27:  # Esc
                return None
            elif key == ord('\t') or key == curses.KEY_DOWN:
                current_focus = (current_focus + 1) % 3
            elif key == curses.KEY_UP:
                current_focus = (current_focus - 1) % 3
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT) and current_focus in (1, 2):
                current_focus = 3 - current_focus  # toggle Cancel <-> OK
            elif key == curses.KEY_ENTER or key in (10, 13):
                if current_focus == 1:
                    return None
                # OK, or Enter in the field submits
                return user_input if user_input else None
            elif current_focus == 0:
                if key in (curses.KEY_BACKSPACE, 127, 8):
                    user_input = user_input[:-1]
                elif 32 <= key <= 126:
                    user_input += chr(key)
    finally:
        curses.curs_set(0)


def show_horizontal_menu(title: str, options: List[str]) -> int:
    """
    Display a horizontal arrow-key menu (curses) for simple choices (Yes/No, OK/Cancel).

    Args:
        title: Menu title/question
        options: List of menu options (displayed horizontally)

    Returns:
        Selected option number (1-based), or 0 if cancelled.
    """
    try:
        return curses.wrapper(show_menu_horizontal_curses, title, options)
    except Exception as e:
        print_error(f"Menu error: {e}")
        return 0


def input_dialog(title: str, prompt: str, password: bool = False) -> Optional[str]:
    """
    Interactive input dialog with Cancel/OK buttons

    Args:
        title: Dialog title
        prompt: Input field label
        password: If True, mask input with asterisks

    Returns:
        User input string or None if cancelled
    """
    try:
        return curses.wrapper(input_dialog_curses, title, prompt, password)
    except Exception as e:
        print_error(f"Input dialog error: {e}")
        return None


def show_text_screen_curses(stdscr, title: str, lines: List[str]) -> None:
    """Framed scrollable read-only text screen. Enter/Esc/q closes it."""
    curses.curs_set(0)
    _init_colors()

    top = 0
    while True:
        stdscr.erase()
        scroll = len(lines) > 1  # recomputed against body below
        y0, x0, body_h, body_w = _draw_frame(
            stdscr, title,
            "↑↓ PgUp/PgDn scroll   Enter/Esc — back" if scroll
            else "Enter/Esc — back")
        max_top = max(0, len(lines) - body_h)
        top = min(max(0, top), max_top)

        for i in range(body_h):
            li = top + i
            if li >= len(lines):
                break
            try:
                stdscr.addstr(y0 + i, x0, lines[li][:max(0, body_w)])
            except curses.error:
                pass

        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('\n'), ord('\r'), 27, ord('q'), ord('Q')):
            return
        elif key == curses.KEY_UP:
            top -= 1
        elif key == curses.KEY_DOWN:
            top += 1
        elif key == curses.KEY_NPAGE:
            top += body_h
        elif key == curses.KEY_PPAGE:
            top -= body_h
        elif key == curses.KEY_HOME:
            top = 0
        elif key == curses.KEY_END:
            top = max_top


def show_text_screen(title: str, lines: List[str]) -> None:
    """Show a scrollable read-only text screen (curses)."""
    try:
        curses.wrapper(show_text_screen_curses, title, lines)
    except Exception as e:
        # Last-resort plain output so information is never lost.
        print_error(f"Screen error: {e}")
        print_header(title)
        for ln in lines:
            print(ln)
        press_enter_to_continue()


def show_wait_screen(title: str, message: str, fn, *args, **kwargs):
    """
    Run a blocking function while showing a framed curses spinner screen.

    stdout/stderr of fn are captured so core print_* output cannot corrupt
    the curses display.

    Returns:
        (result, captured_text). If fn raised, result is the exception object.
    """
    import io
    import threading
    import contextlib

    state = {'result': None, 'done': False}
    buf = io.StringIO()

    def runner():
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                state['result'] = fn(*args, **kwargs)
        except Exception as e:  # surfaced to the caller, never swallowed
            state['result'] = e
        finally:
            state['done'] = True

    def ui(stdscr):
        curses.curs_set(0)
        _init_colors()
        stdscr.nodelay(True)
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        while not state['done']:
            stdscr.erase()
            y0, x0, body_h, body_w = _draw_frame(stdscr, title)
            w = stdscr.getmaxyx()[1]
            text = f"{spinner[i % len(spinner)]} {message}"
            try:
                stdscr.addstr(y0 + body_h // 2, max(x0, (w - len(text)) // 2),
                              text[:max(0, body_w)])
            except curses.error:
                pass
            stdscr.refresh()
            i += 1
            curses.napms(100)
        thread.join()

    try:
        curses.wrapper(ui)
    except Exception:
        # curses failed — run plainly so the operation still happens
        if not state['done']:
            runner()
    return state['result'], buf.getvalue()


def show_progress_screen(title: str, worker) -> tuple:
    """
    Run worker(progress) in a thread while drawing a framed progress screen.

    worker receives `progress(percent, *lines)`: percent is 0-100 or None
    (indeterminate), lines are short status strings shown under the bar.
    stdout/stderr of the worker are captured.

    Returns:
        (result, captured_text). If worker raised, result is the exception.
    """
    import io
    import threading
    import contextlib

    state = {'percent': None, 'lines': (), 'done': False, 'result': None}
    buf = io.StringIO()

    def progress(percent, *lines):
        state['percent'] = percent
        state['lines'] = lines

    def runner():
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                state['result'] = worker(progress)
        except Exception as e:
            state['result'] = e
        finally:
            state['done'] = True

    def ui(stdscr):
        curses.curs_set(0)
        _init_colors()
        stdscr.nodelay(True)
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        while not state['done']:
            stdscr.erase()
            y0, x0, body_h, body_w = _draw_frame(stdscr, title)
            w = stdscr.getmaxyx()[1]
            y = y0 + max(1, body_h // 2 - 1)
            pct = state['percent']
            bar_w = max(10, min(50, body_w - 10))
            try:
                if pct is None:
                    text = f"{spinner[i % len(spinner)]} working..."
                    stdscr.addstr(y, max(x0, (w - len(text)) // 2), text)
                else:
                    filled = int(bar_w * min(100, max(0, pct)) / 100)
                    bar = "█" * filled + "░" * (bar_w - filled)
                    line = f"[{bar}] {pct:3.0f}%"
                    stdscr.addstr(y, max(x0, (w - len(line)) // 2), line[:max(0, body_w)])
                for j, ln in enumerate(state['lines'][:3]):
                    s = str(ln)
                    stdscr.addstr(y + 2 + j, max(x0, (w - len(s)) // 2),
                                  s[:max(0, body_w)])
            except curses.error:
                pass
            stdscr.refresh()
            i += 1
            curses.napms(100)
        thread.join()

    try:
        curses.wrapper(ui)
    except Exception:
        if not state['done']:
            runner()
    return state['result'], buf.getvalue()


def show_confirm_screen(title: str, lines: List[str], yes_label: str = "YES",
                        no_label: str = "NO") -> bool:
    """
    Framed confirmation screen: info lines + < NO > < YES > buttons.
    NO is preselected. Esc/q = NO. Returns True only on explicit YES.
    """
    def ui(stdscr):
        curses.curs_set(0)
        _init_colors()
        current = 0  # 0 = NO (safe default), 1 = YES
        while True:
            stdscr.erase()
            y0, x0, body_h, body_w = _draw_frame(
                stdscr, title, "←→ move   Enter select   Esc cancel")
            w = stdscr.getmaxyx()[1]
            y = y0 + 1
            for ln in lines:
                if y >= y0 + body_h - 2:
                    break
                try:
                    stdscr.addstr(y, x0 + 1, str(ln)[:max(0, body_w - 2)])
                except curses.error:
                    pass
                y += 1
            buttons = [f"< {no_label} >", f"< {yes_label} >"]
            total = sum(len(b) for b in buttons) + 6
            bx = max(x0, (w - total) // 2)
            by = min(y0 + body_h - 1, y + 1)
            for idx, btn in enumerate(buttons):
                try:
                    if idx == current:
                        attr = (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() \
                            else curses.A_REVERSE
                        stdscr.addstr(by, bx, btn, attr)
                    else:
                        stdscr.addstr(by, bx, btn)
                except curses.error:
                    pass
                bx += len(btn) + 6
            stdscr.refresh()
            key = stdscr.getch()
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord('\t')):
                current = 1 - current
            elif key in (ord('\n'), ord('\r')):
                return current == 1
            elif key in (27, ord('q'), ord('Q')):
                return False

    try:
        return bool(curses.wrapper(ui))
    except Exception as e:
        print_error(f"Screen error: {e}")
        return False


def show_settings_screen_curses(stdscr, title: str, items: List[dict]) -> None:
    """menuconfig-style settings screen (single curses session).

    Each item is a dict:
      {'type': 'bool'|'choice'|'string'|'int',
       'label': str,
       'get': callable() -> value,
       'set': callable(value),
       'help': str,                       # optional
       'choices': [(value, label), ...]}  # for 'choice'
    Values are applied immediately via set(); nothing persists across reboot.
    """
    curses.curs_set(0)
    _init_colors()

    def fmt(item) -> str:
        kind = item['type']
        if kind == 'bool':
            return f"[{'*' if item['get']() else ' '}] {item['label']}"
        if kind == 'choice':
            cur = item['get']()
            cur_label = next((lab for val, lab in item['choices'] if val == cur), str(cur))
            return f"    {item['label']} ({cur_label})  --->"
        # string / int
        return f"    {item['label']} ({item['get']()})"

    def inline_help(item):
        stdscr.erase()
        y0, x0, body_h, body_w = _draw_frame(stdscr, item['label'], "any key — back")
        y = y0
        for ln in item.get('help', 'No help available.').split('\n'):
            if y >= y0 + body_h:
                break
            try:
                stdscr.addstr(y, x0 + 1, ln[:max(0, body_w - 2)])
            except curses.error:
                pass
            y += 1
        stdscr.refresh()
        stdscr.getch()

    def inline_choice(item):
        choices = item['choices']
        cur_val = item['get']()
        sel = next((i for i, (val, _) in enumerate(choices) if val == cur_val), 0)
        while True:
            stdscr.erase()
            y0, x0, body_h, body_w = _draw_frame(
                stdscr, item['label'], "↑↓ move   Enter select   Esc cancel")
            for i, (val, lab) in enumerate(choices):
                y = y0 + i
                if y >= y0 + body_h:
                    break
                marker = "(X)" if val == cur_val else "( )"
                line = f"  {marker} {lab}"
                try:
                    if i == sel and curses.has_colors():
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(y, x0 + 1, line[:max(0, body_w - 2)])
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y, x0 + 1, line[:max(0, body_w - 2)])
                except curses.error:
                    pass
            stdscr.refresh()
            key = stdscr.getch()
            if key == curses.KEY_UP and sel > 0:
                sel -= 1
            elif key == curses.KEY_DOWN and sel < len(choices) - 1:
                sel += 1
            elif key in (ord('\n'), ord('\r')):
                item['set'](choices[sel][0])
                return
            elif key in (27, ord('q'), ord('Q')):
                return

    def inline_edit(item):
        digits_only = item['type'] == 'int'
        buf = list(str(item['get']()))
        curses.curs_set(1)
        try:
            while True:
                stdscr.erase()
                y0, x0, body_h, body_w = _draw_frame(
                    stdscr, item['label'], "Enter save   Esc cancel   Backspace delete")
                prompt = f"{item['label']}: "
                text = ''.join(buf)
                try:
                    stdscr.addstr(y0 + body_h // 2, x0 + 1,
                                  (prompt + text)[:max(0, body_w - 2)])
                except curses.error:
                    pass
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('\n'), ord('\r')):
                    value = ''.join(buf)
                    if digits_only:
                        if not value.isdigit():
                            continue
                        item['set'](int(value))
                    else:
                        item['set'](value)
                    return
                elif key == 27:
                    return
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    if buf:
                        buf.pop()
                elif 32 <= key <= 126:
                    if not digits_only or chr(key).isdigit():
                        buf.append(chr(key))
        finally:
            curses.curs_set(0)

    current = 0
    top = 0
    while True:
        stdscr.erase()
        y0, x0, body_h, body_w = _draw_frame(
            stdscr, title,
            "↑↓ move   Space/Enter change   ? help   Esc back   (resets on reboot)")
        y0 += 1  # breathing row under the top border
        body_h = max(1, body_h - 1)
        if current < top:
            top = current
        elif current >= top + body_h:
            top = current - body_h + 1
        top = max(0, min(top, max(0, len(items) - body_h)))

        for i in range(body_h):
            idx = top + i
            if idx >= len(items):
                break
            line = f" {fmt(items[idx])} "
            try:
                if idx == current and curses.has_colors():
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(y0 + i, x0 + 1, line[:max(0, body_w - 2)])
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addstr(y0 + i, x0 + 1, line[:max(0, body_w - 2)])
            except curses.error:
                pass

        stdscr.refresh()

        key = stdscr.getch()
        item = items[current] if items else None
        if key == curses.KEY_UP and current > 0:
            current -= 1
        elif key == curses.KEY_DOWN and current < len(items) - 1:
            current += 1
        elif key == ord('?') and item:
            inline_help(item)
        elif key in (ord(' '), ord('\n'), ord('\r')) and item:
            if item['type'] == 'bool':
                item['set'](not item['get']())
            elif item['type'] == 'choice':
                inline_choice(item)
            elif item['type'] in ('string', 'int'):
                inline_edit(item)
        elif key in (27, ord('q'), ord('Q')):
            return


def show_settings_screen(title: str, items: List[dict]) -> None:
    """Show a menuconfig-style settings screen (curses)."""
    try:
        curses.wrapper(show_settings_screen_curses, title, items)
    except Exception as e:
        print_error(f"Settings screen error: {e}")


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

