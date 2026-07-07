"""
Menu Logic and Navigation for OLED Interface
"""

from input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACK, KEY_HOME, KEY_LEFT, KEY_RIGHT
import config


class Menu:
    """Handle menu display and navigation"""

    def __init__(self, display, input_handler):
        """
        Initialize menu

        Args:
            display: DisplayManager instance
            input_handler: InputHandler instance
        """
        self.display = display
        self.input = input_handler
        self.current_index = 0
        self.menu_stack = []  # For navigation history

    def show_menu(self, title, items):
        """
        Show menu and return selected index or None for back

        Args:
            title: Menu title
            items: List of menu item strings

        Returns:
            Selected index (0-based) or None for back
        """
        self.current_index = 0

        while True:
            self.display.draw_menu(title, items, self.current_index)
            key = self.input.wait_for_key()

            if key == KEY_UP:
                # Don't go above first item
                if self.current_index > 0:
                    self.current_index -= 1
            elif key == KEY_DOWN:
                # Don't go below last item
                if self.current_index < len(items) - 1:
                    self.current_index += 1
            elif key == KEY_LEFT or key == KEY_RIGHT:
                # Ignore left/right
                continue
            elif key == KEY_ENTER:
                return self.current_index
            elif key == KEY_BACK:
                return None  # Go back
            elif key == KEY_HOME:
                return -1  # Go to main menu

    def show_grid_menu(self, items):
        """
        Show 2x2 grid menu and return selected index or None for back

        Args:
            items: List of 4 menu item strings (can have \n for multi-line)

        Returns:
            Selected index (0-based) or None for back
        """
        # Grid position (row, col)
        row = 0
        col = 0

        while True:
            self.display.draw_grid_menu(items, row, col)
            key = self.input.wait_for_key()

            if key == KEY_UP:
                # Move up (stop at edge)
                if row > 0:
                    row -= 1
            elif key == KEY_DOWN:
                # Move down (stop at edge)
                if row < 1:
                    row += 1
            elif key == KEY_LEFT:
                # Move left (stop at edge)
                if col > 0:
                    col -= 1
            elif key == KEY_RIGHT:
                # Move right (stop at edge)
                if col < 1:
                    col += 1
            elif key == KEY_ENTER:
                # Return linear index: row * 2 + col
                return row * 2 + col
            elif key == KEY_BACK:
                return None  # Go back
            elif key == KEY_HOME:
                return -1  # Go to main menu

    def show_message(self, title, message, wait_for_key=True):
        """
        Show message screen

        Args:
            title: Message title
            message: Message text (can be multi-line string)
            wait_for_key: If True, wait for key press before returning

        Returns:
            -1 if HOME pressed, None otherwise
        """
        self.display.draw_message(title, message)
        if wait_for_key:
            key = self.input.wait_for_key()
            if key == KEY_HOME:
                return -1
        return None

    def confirm(self, title, message=None):
        """
        Show Yes/No confirmation

        Args:
            title: Confirmation title
            message: Optional message to show before choices

        Returns:
            -1 if HOME pressed, True if Yes selected, False otherwise
        """
        if message:
            # Show message first, then confirmation menu
            msg_result = self.show_message(title, message, wait_for_key=True)
            if msg_result == -1:
                return -1

        items = ["No", "Yes"]
        result = self.show_menu(title, items)
        if result == -1:
            return -1  # Home
        return result == 1  # Yes selected

    def horizontal_choice(self, title, option1="NO", option2="OK"):
        """
        Show horizontal choice dialog with LEFT/RIGHT navigation

        Args:
            title: Dialog title (can be multi-line with \\n)
            option1: Left option text (default "NO")
            option2: Right option text (default "OK")

        Returns:
            0 for option1 (NO), 1 for option2 (OK), None for BACK
        """
        selected = 0  # Start with NO (left option)

        # Draw initial state BEFORE entering the loop
        self.display.draw_horizontal_choice(title, option1, option2, selected)

        while True:
            key = self.input.wait_for_key()

            if key == KEY_LEFT:
                selected = 0
                self.display.draw_horizontal_choice(title, option1, option2, selected)
            elif key == KEY_RIGHT:
                selected = 1
                self.display.draw_horizontal_choice(title, option1, option2, selected)
            elif key == KEY_ENTER:
                return selected
            elif key == KEY_BACK:
                return None  # Go back
            elif key == KEY_HOME:
                return -1  # Go to main menu

    def show_progress(self, title, message, percent=None):
        """
        Show progress screen (non-blocking)

        Args:
            title: Operation title
            message: Progress message
            percent: Optional progress percentage (0-100)
        """
        self.display.draw_progress(title, message, percent)

    def show_working(self, title, message, frame=0):
        """
        Show working/spinner screen (non-blocking)

        Args:
            title: Operation title
            message: Status message
            frame: Animation frame number
        """
        self.display.draw_spinner(title, message, frame)

    def input_text(self, title, prompt="", initial=""):
        """
        On-screen keyboard for text input with 4x8 grid layout

        Args:
            title: Input screen title (shown in password bar)
            prompt: Optional hint text (e.g., SSID name)
            initial: Initial text value

        Returns:
            Entered text or None if cancelled
        """
        from language import t

        # Define keyboard layouts (4 rows x 8 columns)
        KEYBOARD_LOWERCASE = [
            ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
            ['i', 'j', 'k', 'l', 'm', 'n', 'o', 'p'],
            ['q', 'r', 's', 't', 'u', 'v', 'w', 'x'],
            ['y', 'z', '_', 'Sp', '←', 'OK', 'AB', '']
        ]

        KEYBOARD_UPPERCASE = [
            ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
            ['I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'],
            ['Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X'],
            ['Y', 'Z', '_', 'Sp', '←', 'OK', '12', '']
        ]

        KEYBOARD_NUMBERS = [
            ['0', '1', '2', '3', '4', '5', '6', '7'],
            ['8', '9', '!', '@', '#', '$', '%', '^'],
            ['&', '*', '(', ')', '-', '+', '=', '_'],
            ['.', '/', 'Sp', '←', 'OK', 'ab', '', '']
        ]

        keyboards = [KEYBOARD_LOWERCASE, KEYBOARD_UPPERCASE, KEYBOARD_NUMBERS]

        # State
        password = initial
        mode = 0  # 0=lowercase, 1=uppercase, 2=numbers
        cursor_row = 0
        cursor_col = 0

        while True:
            # Get current keyboard
            current_keyboard = keyboards[mode]

            # Draw keyboard
            self.display.draw_keyboard(password, current_keyboard, cursor_row, cursor_col, prompt)

            # Wait for input
            key = self.input.wait_for_key()

            if key == KEY_UP:
                if cursor_row > 0:
                    cursor_row -= 1
            elif key == KEY_DOWN:
                if cursor_row < 3:
                    cursor_row += 1
            elif key == KEY_LEFT:
                if cursor_col > 0:
                    cursor_col -= 1
            elif key == KEY_RIGHT:
                if cursor_col < 7:
                    cursor_col += 1
            elif key == KEY_ENTER:
                # Select current cell
                char = current_keyboard[cursor_row][cursor_col]

                if char == 'Sp':
                    # Add space
                    password += ' '
                elif char == '←':
                    # Backspace
                    if password:
                        password = password[:-1]
                elif char == 'OK':
                    # Done - return password
                    return password if password else None
                elif char in ['AB', '12', 'ab']:
                    # Switch mode: ab → AB → 12 → ab
                    mode = (mode + 1) % 3
                elif char and char not in ['']:
                    # Add character
                    password += char
            elif key == KEY_BACK:
                # Cancel
                return None
            elif key == KEY_HOME:
                # Go to main menu
                return -1

    def select_from_list(self, title, items, show_index=True, show_counter=True):
        """
        Select from a list with scrolling (title always on top)

        Args:
            title: Selection title (fixed at top)
            items: List of items to select from
            show_index: If True, show index numbers (default: True)
            show_counter: If True, show "1/10" counter in title (default: True)

        Returns:
            Selected index or None if cancelled
        """
        if not items:
            self.show_message(title, "No items available")
            return None

        # Scrollable list with fixed title
        selected = 0
        scroll_offset = 0

        # Calculate max visible items dynamically based on actual heights
        # Pre-calculate heights for all items
        max_text_width = config.MAX_LINE_LENGTH - 2 if show_index else config.MAX_LINE_LENGTH
        item_heights = []
        for item in items:
            wrapped = self.display._wrap_text(str(item), max_text_width, first_line_indent=show_index)[:2]
            item_heights.append(len(wrapped) * 14)

        while True:
            # Calculate how many items can fit on screen
            available_height = self.display.height - 16  # Minus title (14+2)
            cumulative_height = 0
            max_visible = 0

            for i in range(scroll_offset, len(items)):
                if cumulative_height + item_heights[i] <= available_height:
                    cumulative_height += item_heights[i]
                    max_visible += 1
                else:
                    break

            # Ensure at least 1 item is visible
            if max_visible == 0:
                max_visible = 1

            # Calculate visible range
            visible_start = scroll_offset
            visible_end = min(scroll_offset + max_visible, len(items))
            visible_items = items[visible_start:visible_end]

            # Calculate cursor position in visible area
            cursor_pos = selected - scroll_offset

            # Calculate scroll indicators
            can_scroll_up = scroll_offset > 0
            can_scroll_down = visible_end < len(items)

            # Draw list with title
            self._draw_scrollable_list(title, visible_items, cursor_pos,
                                       selected + 1, len(items),
                                       visible_start + 1,
                                       can_scroll_up, can_scroll_down,
                                       show_index, show_counter)

            # Wait for input
            key = self.input.wait_for_key()

            if key == KEY_UP:
                if selected > 0:
                    selected -= 1
                    # Scroll up if needed
                    if selected < scroll_offset:
                        scroll_offset = selected
            elif key == KEY_DOWN:
                if selected < len(items) - 1:
                    selected += 1
                    # Scroll down if needed
                    if selected >= scroll_offset + max_visible:
                        scroll_offset = selected - max_visible + 1
            elif key == KEY_ENTER:
                return selected
            elif key == KEY_BACK:
                return None  # Go back
            elif key == KEY_HOME:
                return -1  # Go to main menu

    def _draw_scrollable_list(self, title, items, cursor_pos, current_num, total_num,
                              first_visible_num=1, can_scroll_up=False, can_scroll_down=False,
                              show_index=True, show_counter=True):
        """
        Draw scrollable list with fixed title at top

        Args:
            title: Fixed title at top
            items: Visible items
            cursor_pos: Cursor position in visible items
            current_num: Current item number (1-based)
            total_num: Total number of items
            first_visible_num: Number of first visible item (1-based)
            can_scroll_up: Whether can scroll up
            can_scroll_down: Whether can scroll down
            show_index: Whether to show item numbers
            show_counter: Whether to show "1/10" counter in title
        """
        # Clear entire screen first (PIL Image)
        from PIL import Image
        self.display.image = Image.new('1', (self.display.width, self.display.height), color=0)
        from PIL import ImageDraw
        self.display.draw = ImageDraw.Draw(self.display.image)

        y = 0

        # Draw title with optional counter and scroll indicators
        if show_counter:
            title_base = f"{title} {current_num}/{total_num}"
        else:
            title_base = title

        # Add scroll indicators
        scroll_indicator = ""
        if can_scroll_up and can_scroll_down:
            scroll_indicator = " ↕"
        elif can_scroll_up:
            scroll_indicator = " ↑"
        elif can_scroll_down:
            scroll_indicator = " ↓"

        title_with_all = title_base + scroll_indicator
        truncated_title = self.display._truncate(title_with_all, config.MAX_LINE_LENGTH)
        self.display.draw.text((0, y), truncated_title,
                              font=self.display.font_small, fill=1)
        y += 14

        # Separator line
        self.display.draw.line((0, y, self.display.width - 1, y), fill=1)
        y += 2

        # Calculate text offset if showing numbers
        text_offset = 15 if show_index else 2

        # Draw visible items (check bounds)
        for i, item in enumerate(items):
            item_number = first_visible_num + i

            # Wrap text to multiple lines (max 2 lines per item)
            # Reduce max width if showing numbers
            max_text_width = config.MAX_LINE_LENGTH - 2 if show_index else config.MAX_LINE_LENGTH
            wrapped_lines = self.display._wrap_text(str(item), max_text_width, first_line_indent=show_index)[:2]

            # Calculate item height (14px per line)
            item_height = len(wrapped_lines) * 14

            # Make sure we don't overflow screen
            if y + item_height > self.display.height:
                break

            # Draw background highlight if selected
            if i == cursor_pos:
                self.display.draw.rectangle((0, y, self.display.width - 1, y + item_height - 1), fill=1)

            # Draw item number
            if show_index:
                num_text = f"{item_number}."
                if i == cursor_pos:
                    self.display.draw.text((2, y + 1), num_text,
                                          font=self.display.font_small, fill=0)
                else:
                    self.display.draw.text((2, y + 1), num_text,
                                          font=self.display.font_small, fill=1)

            # Draw each line
            line_y = y
            for line_idx, line in enumerate(wrapped_lines):
                # First line uses text_offset, subsequent lines start from left edge
                x_pos = text_offset if line_idx == 0 else 2

                if i == cursor_pos:
                    # White text on black background (inverted)
                    self.display.draw.text((x_pos, line_y + 1), line,
                                          font=self.display.font_small, fill=0)
                else:
                    # Black text on white background
                    self.display.draw.text((x_pos, line_y + 1), line,
                                          font=self.display.font_small, fill=1)
                line_y += 14

            y += item_height

        self.display._update_display()

