"""
Utility functions for Rescue Console Application
"""

import os
import sys
import subprocess
import shutil
import time
import socket
from datetime import datetime
from typing import Tuple, Optional, List
import config

# Try to import curses for interactive menu
try:
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
    import config

    # For critical actions, show warning
    if require_yes:
        print()
        print_warning("⚠️  CRITICAL ACTION - PLEASE CONFIRM")

    print_info(prompt)
    print()

    for attempt in range(1, max_attempts + 1):
        # Use interactive menu if enabled
        if config.INTERACTIVE_MENU and CURSES_AVAILABLE:
            try:
                choice = show_menu(
                    "Confirm Action",
                    ["✓ YES - Proceed with operation", "✗ NO - Cancel operation"]
                )

                if choice == 1:
                    return True
                elif choice == 2:
                    return False
                else:
                    # Choice 0 = cancel/escape
                    return False

            except Exception:
                # Fallback to text input on error
                pass

        # Fallback: classic text input
        if require_yes:
            response = input(f"Type 'yes' to confirm (attempt {attempt}/{max_attempts}): ").strip().lower()
            if response == "yes":
                return True
            elif response in ['no', 'n', 'cancel']:
                return False
            # Invalid input - try again
            print_warning(f"Invalid input. Please type 'yes' to confirm or 'no' to cancel.")
        else:
            response = input(f"Confirm (y/n, attempt {attempt}/{max_attempts}): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            # Invalid input - try again
            print_warning(f"Invalid input. Please type 'y' for yes or 'n' for no.")

        print()

    # Max attempts reached
    print_error(f"Maximum attempts ({max_attempts}) reached. Operation cancelled.")
    return False


def show_progress_bar(current: int, total: int, width: int = 50, prefix: str = "Progress"):
    """Display a progress bar"""
    if total <= 0:
        return

    percentage = min(100, (current * 100) // total)
    filled = (width * current) // total
    bar = "█" * filled + "░" * (width - filled)

    print(f"\r{prefix}: |{bar}| {percentage}%", end='', flush=True)

    if current >= total:
        print()  # New line when complete


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
    stdscr.clear()

    # Initialize colors if supported
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Title
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Normal

    current_row = 0

    while True:
        stdscr.clear()
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
    stdscr.clear()

    # Initialize colors if supported
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Title
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Normal

    current_option = 0

    while True:
        stdscr.clear()
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
    Display menu and get user choice
    Uses interactive curses menu if enabled and available, otherwise falls back to numbered menu

    Args:
        title: Menu title
        options: List of menu options

    Returns:
        Selected option number (1-based), or 0 for invalid
    """
    # Try interactive menu if enabled
    if config.INTERACTIVE_MENU and CURSES_AVAILABLE:
        try:
            choice = curses.wrapper(show_menu_interactive_curses, title, options)
            if choice > 0:
                return choice
            # If cancelled (choice == 0), fall through to classic menu
        except Exception as e:
            # If curses fails, fall back to classic menu
            print_error(f"Interactive menu failed: {e}, falling back to classic menu")
            pass  # Continue to classic menu

    # Classic numbered menu (fallback)
    print_header(title)

    for idx, option in enumerate(options, 1):
        print(f"  {idx}. {option}")

    print()

    try:
        choice = input("Enter your choice: ").strip()
        choice_num = int(choice)
        if 1 <= choice_num <= len(options):
            return choice_num
        else:
            print_error(f"Invalid choice. Please enter 1-{len(options)}")
            return 0
    except ValueError:
        print_error("Invalid input. Please enter a number.")
        return 0
    except KeyboardInterrupt:
        print("\n")
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
    stdscr.clear()

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
        stdscr.clear()
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
    Display horizontal menu (for simple choices like Yes/No, OK/Cancel)
    Uses interactive curses menu if enabled and available, otherwise falls back to numbered menu

    Args:
        title: Menu title/question
        options: List of menu options (will be displayed horizontally)

    Returns:
        Selected option number (1-based), or 0 for invalid
    """
    # Try interactive horizontal menu if enabled
    if config.INTERACTIVE_MENU and CURSES_AVAILABLE:
        try:
            choice = curses.wrapper(show_menu_horizontal_curses, title, options)
            if choice > 0:
                return choice
            # If cancelled, fall through to classic menu
        except Exception as e:
            # If curses fails, fall back to classic menu
            print_error(f"Interactive menu failed: {e}, falling back to classic menu")
            pass

    # Classic numbered menu (fallback)
    print_header(title)

    for idx, option in enumerate(options, 1):
        print(f"  {idx}. {option}")

    print()

    try:
        choice = input("Enter your choice: ").strip()
        choice_num = int(choice)
        if 1 <= choice_num <= len(options):
            return choice_num
        else:
            print_error(f"Invalid choice. Please enter 1-{len(options)}")
            return 0
    except ValueError:
        print_error("Invalid input. Please enter a number.")
        return 0
    except KeyboardInterrupt:
        print("\n")
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
    # Try interactive dialog if enabled
    if config.INTERACTIVE_MENU and CURSES_AVAILABLE:
        try:
            result = curses.wrapper(input_dialog_curses, title, prompt, password)
            return result
        except Exception as e:
            # If curses fails, fall back to simple input
            print_error(f"Interactive dialog failed: {e}, falling back to simple input")
            pass

    # Fallback to simple input
    print_header(title)
    print_info(prompt)
    print()

    try:
        if password:
            import getpass
            user_input = getpass.getpass("Password: ")
        else:
            user_input = input(f"{prompt}: ").strip()
        return user_input if user_input else None
    except KeyboardInterrupt:
        print("\n")
        return None
    except EOFError:
        return None


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

