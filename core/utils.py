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
    stdscr.erase()

    # Initialize colors if supported
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Title
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Normal

    current_row = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Compact title for small terminals (serial console, SSH)
        title_padded = f"  {title.upper()}  "
        title_width = len(title_padded) + 4  # Minimal padding
        title_display = title_padded.center(title_width)

        # Draw title - compact version (3 lines total)
        start_x = max(0, (w - title_width - 2) // 2)

        if curses.has_colors():
            stdscr.attron(curses.color_pair(2) | curses.A_BOLD)

        # Single line title with border
        stdscr.addstr(0, start_x, "╔" + "═" * title_width + "╗")
        stdscr.addstr(1, start_x, "║" + title_display + "║")
        stdscr.addstr(2, start_x, "╚" + "═" * title_width + "╝")

        if curses.has_colors():
            stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        # Display options (compact for small terminals)
        start_y = 4  # Start below title (which now takes 3 lines)
        line_spacing = 4  # Better spacing for visibility (selected item takes 3 lines + 1 gap)

        # Calculate padding based on screen size for bigger visual appearance
        padding_multiplier = max(2, w // 40)  # More padding on wider screens

        for idx, option in enumerate(options):
            y = start_y + (idx * line_spacing)
            if y >= h - 4:  # Don't overflow screen (reduced margin)
                break

            # Format option text
            option_display = option

            if idx == current_row:
                # Highlighted option - compact (3 lines: border + text + border)
                prefix = "►  "
                number = f"{idx + 1}."

                text_core = f"{prefix}{number} {option_display}"
                text = f" {text_core} "

                # Truncate if too long
                if len(text) > w - 10:
                    text = text[:w - 13] + "..."

                # Center the menu item
                start_x = max(2, (w - len(text)) // 2)

                if curses.has_colors():
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)

                # Draw TOP border (compact)
                border = "─" * len(text)
                if y > 0 and y < h - 1:
                    stdscr.addstr(y, start_x, border)

                # Draw main text line (BOLD + REVERSE)
                if y + 1 < h - 1:
                    stdscr.addstr(y + 1, start_x, text)

                # Draw BOTTOM border (compact)
                if y + 2 < h - 1:
                    stdscr.addstr(y + 2, start_x, border)

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)
            else:
                # Normal option - single line
                prefix = "   "
                number = f"{idx + 1}."
                text = f"{prefix}{number} {option_display}"

                # Truncate if too long
                if len(text) > w - 10:
                    text = text[:w - 13] + "..."

                # Center the menu item
                start_x = max(2, (w - len(text)) // 2)

                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))

                # Draw single line for non-selected items (middle line of 3-line spacing)
                if y + 1 < h - 1:
                    stdscr.addstr(y + 1, start_x, text)

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

        # Display web app info if running (before instructions)
        web_port = 8124
        web_running = check_web_app_status("localhost", web_port)
        if web_running:
            local_ip = get_local_ip()
            if local_ip:
                web_url = f"http://{local_ip}:{web_port}"
            else:
                web_url = f"http://localhost:{web_port}"
            web_info = f"Web: {web_url}"
            # Truncate if too long
            if len(web_info) > w - 4:
                web_info = web_info[:w - 7] + "..."
            web_x = max(2, (w - len(web_info)) // 2)
            if h - 4 >= 0:
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3) | curses.A_DIM)
                stdscr.addstr(h - 4, web_x, web_info)
                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3) | curses.A_DIM)

        # Display instructions (compact for small terminals)
        instructions = "↑↓: Navigate  |  Enter: Select  |  1-9: Jump"

        if len(instructions) < w - 4:
            instr_x = max(2, (w - len(instructions)) // 2)

            # Draw instructions (compact - 2 lines)
            if h - 2 >= 0:
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))

                # Instructions text
                stdscr.addstr(h - 2, instr_x, instructions)

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

        stdscr.refresh()

        # Get user input
        key = stdscr.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(options) - 1:
            current_row += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:  # Enter key
            return current_row + 1
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
    stdscr.erase()

    # Initialize colors if supported
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Title
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Normal

    current_option = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Display title
        title_lines = []
        # Split long title into multiple lines
        max_title_width = min(w - 10, 80)
        words = title.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= max_title_width:
                current_line += (word + " ")
            else:
                if current_line:
                    title_lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            title_lines.append(current_line.strip())

        # Draw title centered
        start_y = max(2, (h - 10) // 2)
        if curses.has_colors():
            stdscr.attron(curses.color_pair(2) | curses.A_BOLD)

        for idx, line in enumerate(title_lines):
            x = max(0, (w - len(line)) // 2)
            if start_y + idx < h - 8:
                stdscr.addstr(start_y + idx, x, line)

        if curses.has_colors():
            stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        # Calculate horizontal layout for options
        options_y = start_y + len(title_lines) + 3

        # Calculate spacing
        total_options_width = sum(len(opt) + 6 for opt in options)  # +6 for padding and borders
        spacing = 4
        total_width = total_options_width + spacing * (len(options) - 1)

        # Start x position to center all options
        start_x = max(2, (w - total_width) // 2)

        # Draw options horizontally
        current_x = start_x
        for idx, option in enumerate(options):
            # Create button text with padding
            button_text = f" {option} "
            button_width = len(button_text) + 2  # +2 for borders

            if idx == current_option:
                # Selected option - highlighted
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)

                # Draw button with borders
                if options_y < h - 4 and current_x + button_width < w - 2:
                    border_line = "─" * len(button_text)
                    stdscr.addstr(options_y, current_x, f"┌{border_line}┐")
                    stdscr.addstr(options_y + 1, current_x, f"│{button_text}│")
                    stdscr.addstr(options_y + 2, current_x, f"└{border_line}┘")

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)
            else:
                # Normal option
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))

                # Draw simple button
                if options_y + 1 < h - 4 and current_x + button_width < w - 2:
                    stdscr.addstr(options_y + 1, current_x, f" {button_text} ")

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

            current_x += button_width + spacing

        # Display instructions
        instructions = "←→: Navigate  |  Enter: Select  |  1-9: Jump"
        if len(instructions) < w - 4:
            instr_x = max(2, (w - len(instructions)) // 2)
            if h - 2 >= 0:
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))
                stdscr.addstr(h - 2, instr_x, instructions)
                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

        stdscr.refresh()

        # Get user input
        key = stdscr.getch()

        if key == curses.KEY_LEFT and current_option > 0:
            current_option -= 1
        elif key == curses.KEY_RIGHT and current_option < len(options) - 1:
            current_option += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:  # Enter key
            return current_option + 1
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
    Interactive input dialog with horizontal menu (Cancel/OK)

    Args:
        stdscr: Curses screen object
        title: Dialog title
        prompt: Input field label
        password: If True, mask input with asterisks

    Returns:
        User input string or None if cancelled
    """
    curses.curs_set(1)  # Show cursor
    stdscr.erase()

    # Initialize colors
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Title
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Normal
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Input field

    user_input = ""
    current_focus = 0  # 0 = input field, 1 = Cancel, 2 = OK

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Display title
        start_y = max(2, (h - 15) // 2)
        if curses.has_colors():
            stdscr.attron(curses.color_pair(2) | curses.A_BOLD)

        title_x = max(0, (w - len(title)) // 2)
        if start_y < h - 10:
            stdscr.addstr(start_y, title_x, title)

        if curses.has_colors():
            stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        # Display prompt
        prompt_y = start_y + 3
        prompt_x = max(2, (w - len(prompt) - 30) // 2)
        if prompt_y < h - 8:
            stdscr.addstr(prompt_y, prompt_x, prompt)

        # Input field
        input_y = prompt_y + 2
        input_width = min(40, w - 10)
        input_x = max(2, (w - input_width) // 2)

        # Draw input field background
        if input_y < h - 6:
            if curses.has_colors() and current_focus == 0:
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
            elif curses.has_colors():
                stdscr.attron(curses.color_pair(4))

            # Draw input box
            display_text = user_input  # Always show actual text
            # Truncate if too long
            if len(display_text) > input_width - 4:
                display_text = display_text[-(input_width - 4):]

            input_line = f" {display_text:<{input_width - 2}} "
            stdscr.addstr(input_y, input_x, input_line)

            if curses.has_colors():
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD if current_focus == 0 else curses.color_pair(4))

            # Position cursor in input field if focused
            if current_focus == 0:
                cursor_x = input_x + 1 + min(len(display_text), input_width - 3)
                if cursor_x < w - 1:
                    stdscr.move(input_y, cursor_x)

        # Horizontal menu (Cancel / OK)
        menu_y = input_y + 3
        options = ["Cancel", "OK"]

        # Calculate spacing
        button_width_cancel = len("Cancel") + 4
        button_width_ok = len("OK") + 4
        spacing = 6
        total_width = button_width_cancel + spacing + button_width_ok
        menu_x = max(2, (w - total_width) // 2)

        # Draw Cancel button
        if menu_y < h - 4:
            cancel_text = " Cancel "
            if current_focus == 1:
                # Selected
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)

                border = "─" * len(cancel_text)
                stdscr.addstr(menu_y, menu_x, f"┌{border}┐")
                stdscr.addstr(menu_y + 1, menu_x, f"│{cancel_text}│")
                stdscr.addstr(menu_y + 2, menu_x, f"└{border}┘")

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)
            else:
                # Normal
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))
                stdscr.addstr(menu_y + 1, menu_x, f" {cancel_text} ")
                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

        # Draw OK button
        ok_x = menu_x + button_width_cancel + spacing
        if menu_y < h - 4 and ok_x < w - button_width_ok:
            ok_text = "  OK  "
            if current_focus == 2:
                # Selected
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)

                border = "─" * len(ok_text)
                stdscr.addstr(menu_y, ok_x, f"┌{border}┐")
                stdscr.addstr(menu_y + 1, ok_x, f"│{ok_text}│")
                stdscr.addstr(menu_y + 2, ok_x, f"└{border}┘")

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)
            else:
                # Normal
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))
                stdscr.addstr(menu_y + 1, ok_x, f" {ok_text} ")
                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

        # Instructions
        if current_focus == 0:
            instructions = "Type password | Tab/↓: Move to buttons | Enter: Confirm"
        else:
            instructions = "←→: Navigate buttons | ↑/Tab: Back to input | Enter: Select"

        if len(instructions) < w - 4:
            instr_x = max(2, (w - len(instructions)) // 2)
            if h - 2 >= 0:
                if curses.has_colors():
                    stdscr.attron(curses.color_pair(3))
                stdscr.addstr(h - 2, instr_x, instructions)
                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(3))

        stdscr.refresh()

        # Get user input
        try:
            key = stdscr.getch()
        except:
            key = -1

        if current_focus == 0:
            # Input field focused
            if key == curses.KEY_ENTER or key in [10, 13]:
                # Enter in input field = submit (OK)
                return user_input
            elif key == 9 or key == curses.KEY_DOWN:  # Tab or Down arrow
                current_focus = 1  # Move to Cancel button
            elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                # Backspace
                if user_input:
                    user_input = user_input[:-1]
            elif key == 27:  # Escape
                return None
            elif 32 <= key <= 126:  # Printable characters
                user_input += chr(key)
        else:
            # Buttons focused
            if key == curses.KEY_LEFT:
                current_focus = 1  # Cancel
            elif key == curses.KEY_RIGHT:
                current_focus = 2  # OK
            elif key == 9 or key == curses.KEY_UP:  # Tab or Up arrow
                current_focus = 0  # Back to input field
            elif key == curses.KEY_ENTER or key in [10, 13]:
                if current_focus == 1:
                    return None  # Cancel
                else:
                    return user_input  # OK
            elif key == 27:  # Escape
                return None


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
    """Scrollable read-only text screen. Enter/Esc/q closes it."""
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)    # title
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # hint

    top = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Centered single-line title box
        label = f"  {title.upper()}  "
        tw = len(label)
        sx = max(0, (w - tw - 2) // 2)
        if curses.has_colors():
            stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
        try:
            stdscr.addstr(0, sx, "╔" + "═" * tw + "╗")
            stdscr.addstr(1, sx, "║" + label + "║")
            stdscr.addstr(2, sx, "╚" + "═" * tw + "╝")
        except curses.error:
            pass
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        body_top = 4
        body_h = max(1, h - body_top - 1)   # keep the last line for the hint
        max_top = max(0, len(lines) - body_h)
        top = min(max(0, top), max_top)

        for i in range(body_h):
            li = top + i
            if li >= len(lines):
                break
            try:
                stdscr.addstr(body_top + i, 2, lines[li][:max(0, w - 3)])
            except curses.error:
                pass

        if len(lines) > body_h:
            hint = "  ↑↓ PgUp/PgDn scroll    Enter/Esc/q — back"
        else:
            hint = "  Enter/Esc/q — back"
        if curses.has_colors():
            stdscr.attron(curses.color_pair(4))
        try:
            stdscr.addstr(h - 1, 0, hint[:max(0, w - 1)])
        except curses.error:
            pass
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(4))

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


def _draw_title_box(stdscr, title: str) -> None:
    """Draw the standard centered single-line title box on rows 0-2."""
    h, w = stdscr.getmaxyx()
    label = f"  {title.upper()}  "
    tw = len(label)
    sx = max(0, (w - tw - 2) // 2)
    if curses.has_colors():
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
    try:
        stdscr.addstr(0, sx, "╔" + "═" * tw + "╗")
        stdscr.addstr(1, sx, "║" + label + "║")
        stdscr.addstr(2, sx, "╚" + "═" * tw + "╝")
    except curses.error:
        pass
    if curses.has_colors():
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)


def show_wait_screen(title: str, message: str, fn, *args, **kwargs):
    """
    Run a blocking function while showing a curses spinner screen.

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
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        stdscr.nodelay(True)
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        while not state['done']:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            _draw_title_box(stdscr, title)
            try:
                stdscr.addstr(h // 2, max(0, (w - len(message) - 2) // 2),
                              f"{spinner[i % len(spinner)]} {message}"[:w - 1])
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
    Run worker(progress) in a thread while drawing a curses progress screen.

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
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        stdscr.nodelay(True)
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        while not state['done']:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            _draw_title_box(stdscr, title)
            y = h // 2 - 1
            pct = state['percent']
            bar_w = max(10, min(50, w - 14))
            try:
                if pct is None:
                    stdscr.addstr(y, max(0, (w - 12) // 2),
                                  f"{spinner[i % len(spinner)]} working...")
                else:
                    filled = int(bar_w * min(100, max(0, pct)) / 100)
                    bar = "█" * filled + "░" * (bar_w - filled)
                    line = f"[{bar}] {pct:3.0f}%"
                    stdscr.addstr(y, max(0, (w - len(line)) // 2), line[:w - 1])
                for j, ln in enumerate(state['lines'][:3]):
                    stdscr.addstr(y + 2 + j, max(0, (w - len(ln)) // 2), str(ln)[:w - 1])
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
    Curses confirmation screen: info lines + horizontal NO/YES buttons.
    NO is preselected. Esc/q = NO. Returns True only on explicit YES.
    """
    def ui(stdscr):
        curses.curs_set(0)
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        current = 0  # 0 = NO (safe default), 1 = YES
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            _draw_title_box(stdscr, title)
            y = 4
            for ln in lines:
                if y >= h - 4:
                    break
                try:
                    stdscr.addstr(y, 2, str(ln)[:max(0, w - 3)])
                except curses.error:
                    pass
                y += 1
            labels = [f"  {no_label}  ", f"  {yes_label}  "]
            total = len(labels[0]) + len(labels[1]) + 6
            x = max(0, (w - total) // 2)
            by = min(h - 2, y + 2)
            for idx, lab in enumerate(labels):
                try:
                    if idx == current and curses.has_colors():
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(by, x, lab)
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(by, x, lab)
                except curses.error:
                    pass
                x += len(lab) + 6
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
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)   # selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)    # title
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # hint

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

    def hint_bar(text: str):
        h, w = stdscr.getmaxyx()
        if curses.has_colors():
            stdscr.attron(curses.color_pair(4))
        try:
            stdscr.addstr(h - 1, 0, text[:max(0, w - 1)])
        except curses.error:
            pass
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(4))

    def inline_help(item):
        stdscr.erase()
        _draw_title_box(stdscr, item['label'])
        y = 4
        h, w = stdscr.getmaxyx()
        for ln in item.get('help', 'No help available.').split('\n'):
            if y >= h - 2:
                break
            try:
                stdscr.addstr(y, 2, ln[:max(0, w - 3)])
            except curses.error:
                pass
            y += 1
        hint_bar("  any key — back")
        stdscr.refresh()
        stdscr.getch()

    def inline_choice(item):
        choices = item['choices']
        cur_val = item['get']()
        sel = next((i for i, (val, _) in enumerate(choices) if val == cur_val), 0)
        while True:
            stdscr.erase()
            _draw_title_box(stdscr, item['label'])
            h, w = stdscr.getmaxyx()
            for i, (val, lab) in enumerate(choices):
                y = 4 + i
                if y >= h - 2:
                    break
                marker = "(X)" if val == cur_val else "( )"
                line = f"  {marker} {lab}"
                try:
                    if i == sel and curses.has_colors():
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(y, 2, line[:max(0, w - 3)])
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y, 2, line[:max(0, w - 3)])
                except curses.error:
                    pass
            hint_bar("  ↑↓ move   Enter — select   Esc — cancel")
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
                _draw_title_box(stdscr, item['label'])
                h, w = stdscr.getmaxyx()
                prompt = f"{item['label']}: "
                text = ''.join(buf)
                try:
                    stdscr.addstr(h // 2, 2, (prompt + text)[:max(0, w - 3)])
                except curses.error:
                    pass
                hint_bar("  Enter — save   Esc — cancel   Backspace — delete")
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
        _draw_title_box(stdscr, title)
        h, w = stdscr.getmaxyx()
        body_top = 4
        body_h = max(1, h - body_top - 1)
        top = min(max(0, current - body_h + 1), max(0, len(items) - body_h), top)
        if current < top:
            top = current
        elif current >= top + body_h:
            top = current - body_h + 1

        for i in range(body_h):
            idx = top + i
            if idx >= len(items):
                break
            line = fmt(items[idx])
            try:
                if idx == current and curses.has_colors():
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(body_top + i, 2, line[:max(0, w - 3)])
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addstr(body_top + i, 2, line[:max(0, w - 3)])
            except curses.error:
                pass

        hint_bar("  ↑↓ move   Space/Enter — change   ? — help   Esc/q — back   (runtime only, resets on reboot)")
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

