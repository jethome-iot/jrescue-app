"""
Menu Logic and Navigation for OLED Interface
"""

from input import KEY_UP, KEY_DOWN, KEY_ENTER, KEY_BACK, KEY_HOME, KEY_LEFT, KEY_RIGHT
import threading
import time
import config
from language import t


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
        self._main_selection = 0

    def show_menu(self, title, items, compact=False, right='', initial_index=0):
        """
        Show menu and return selected index or None for back

        Args:
            title: Menu title
            items: List of menu item strings

        Returns:
            Selected index (0-based) or None for back
        """
        if not items:
            return None
        self.current_index = min(max(0, initial_index), len(items)-1)

        while True:
            self.display.draw_menu(title, items, self.current_index, compact=compact, right=right)
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

    def show_main_menu(self, items):
        """Navigate the four-item grid without wrapping across its edges."""
        if not items:
            return None
        self._main_selection = min(self._main_selection, len(items)-1)
        while True:
            selected = self._main_selection
            self.display.draw_main_menu(items, selected)
            key = self.input.wait_for_key()
            if key == KEY_UP and selected >= 2:
                self._main_selection -= 2
            elif key == KEY_DOWN and selected+2 < len(items):
                self._main_selection += 2
            elif key == KEY_LEFT and selected % 2 == 1:
                self._main_selection -= 1
            elif key == KEY_RIGHT and selected % 2 == 0 and selected+1 < len(items):
                self._main_selection += 1
            elif key == KEY_ENTER:
                return selected
            elif key == KEY_BACK:
                return None
            elif key == KEY_HOME:
                self._main_selection = 0
                return -1

    def show_message(self, title, message, wait_for_key=True, success=False):
        """
        Show message screen

        Args:
            title: Message title
            message: Message text (can be multi-line string)
            wait_for_key: If True, wait for key press before returning

        Returns:
            -1 if HOME pressed, None otherwise
        """
        if success:
            for frame in range(5):
                self.display.draw_success(title, message, frame/4, wait_for_key)
                if frame < 4:
                    time.sleep(1/config.OLED_ANIMATION_FPS)
        else:
            self.display.draw_message(title, message, wait_for_key=wait_for_key)
        if wait_for_key:
            key = self.input.wait_for_key()
            if key == KEY_HOME:
                return -1
        return None

    def show_network_status(self, title, interface, link, ip):
        """Display a compact wired status page until acknowledgement or Home."""
        self.display.draw_network_status(title, interface, link, ip)
        return -1 if self.input.wait_for_key() == KEY_HOME else None

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

        items = [t('no'), t('yes')]
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

    def show_progress(self, title, message, percent=None, detail=''):
        """
        Show progress screen (non-blocking)

        Args:
            title: Operation title
            message: Progress message
            percent: Optional progress percentage (0-100)
        """
        self.display.draw_progress(title, message, percent, detail)

    def hold_to_confirm(self, title, line1, line2, seconds=3.0):
        """Require a fresh continuous center hold; releases reset the action."""
        self.display.draw_hold_confirmation(title, line1, line2, 0)
        self.input.flush_events()
        armed = KEY_ENTER not in self.input.get_pressed_keys()
        started = None
        rollback = None

        def progress(now):
            if started is not None:
                return min(100, 100*(now-started)/seconds)
            if rollback is not None:
                value, released = rollback
                return max(0, value*(1-(now-released)/0.3))
            return 0

        try:
            while True:
                events = self.input.read_key_events(timeout=0.1)
                now = time.monotonic()
                for code, value in events:
                    if value == 1 and code == KEY_HOME:
                        return -1
                    if value == 1 and code in (KEY_BACK, KEY_LEFT):
                        return None
                    if code != KEY_ENTER or value == 2:
                        continue
                    if value == 0:
                        if started is not None:
                            rollback = (progress(now), now)
                            started = None
                        armed = True
                    elif value == 1 and armed and started is None:
                        started, rollback, armed = now, None, False

                # Also check the real key state before completing a hold: a
                # missed release event must never cause an unintended reboot.
                if KEY_ENTER not in self.input.get_pressed_keys():
                    if started is not None:
                        rollback = (progress(now), now)
                        started = None
                    armed = True
                percent = progress(now)
                self.display.draw_hold_confirmation(title, line1, line2, percent)
                if started is not None and percent >= 100:
                    return True
                if rollback is not None and percent <= 0:
                    rollback = None
        finally:
            self.input.flush_events()

    def show_working(self, title, message, frame=0):
        """
        Show working/spinner screen (non-blocking)

        Args:
            title: Operation title
            message: Status message
            frame: Animation frame number
        """
        self.display.draw_spinner(title, message, frame)

    def run_working(self, title, message, worker, *args, **kwargs):
        """Animate a blocking operation without running any drawing in its thread."""
        return self._run_operation(title, message, lambda report: worker(*args, **kwargs), False)

    def run_progress(self, title, message, worker):
        """Run worker(progress_cb) once and draw its actual progress on the UI thread."""
        return self._run_operation(title, message, worker, True)

    def _run_operation(self, title, message, worker, use_progress):
        """Keep the operation alive even if drawing fails; never start it twice."""
        done = threading.Event()
        lock = threading.Lock()
        state = {'percent': None, 'lines': (), 'result': None, 'error': None}

        def report(percent, *lines):
            with lock:
                state['percent'], state['lines'] = percent, lines

        def run():
            try:
                state['result'] = worker(report)
            except Exception as exc:
                state['error'] = exc
            finally:
                done.set()

        thread = threading.Thread(target=run)
        thread.start()
        frame = 0
        try:
            while not done.is_set():
                with lock:
                    percent, lines = state['percent'], state['lines']
                if use_progress and percent is not None:
                    self.show_progress(title, message, percent, str(lines[-1]) if lines else '')
                else:
                    self.show_working(title, message, frame)
                frame += 1
                done.wait(1 / config.OLED_ANIMATION_FPS)
            if use_progress and state['percent'] is not None and state['error'] is None:
                self.show_progress(title, message, state['percent'],
                                   str(state['lines'][-1]) if state['lines'] else '')
        finally:
            thread.join()
            self.input.flush_events()
        if state['error'] is not None:
            raise state['error']
        return state['result']

    def input_text(self, title, prompt="", initial=""):
        """Edit a password using the full QWERTY keyboard and explicit mode keys."""
        from keyboard_layout import KeyboardState

        state = KeyboardState(initial)
        directions = {KEY_UP: 'up', KEY_DOWN: 'down', KEY_LEFT: 'left', KEY_RIGHT: 'right'}
        blink_started = time.monotonic()
        while True:
            phase = (time.monotonic()-blink_started)/0.5
            self.display.draw_keyboard(state.value, state.rows, state.row, state.col,
                                       t('keyboard_password'), state.shift, state=state,
                                       cursor_visible=int(phase) % 2 == 0)
            key = self.input.wait_for_key(timeout=max(0.01, (1-phase % 1)*0.5))
            if key is None:
                continue
            blink_started = time.monotonic()
            if key == KEY_ENTER:
                if state.activate():
                    return state.value or None
            elif key == KEY_BACK:
                return None
            elif key == KEY_HOME:
                return -1
            elif key in directions:
                state.move(directions[key])

    def select_from_list(self, title, items, show_index=True, show_counter=True, icons=None,
                         compact=False):
        """
        Select from a list with scrolling (title always on top)

        Args:
            title: Selection title (fixed at top)
            items: List of items to select from
            show_index: If True, show index numbers (default: True)
            show_counter: If True, show "1/10" counter in title (default: True)
            compact: Use smaller names and closer wrapped lines for Wi-Fi SSIDs

        Returns:
            Selected index or None if cancelled
        """
        if not items:
            self.show_message(title, "No items available")
            return None

        # Scrollable list with fixed title
        selected = 0
        scroll_offset = 0

        item_heights = [self.display.list_item_height(item, show_index,
                                                     icons[index] if icons else None, compact=compact)
                        for index, item in enumerate(items)]

        def count_visible(offset):
            available = self.display.height - self.display.renderer.BODY_TOP
            used = 0
            count = 0
            for height in item_heights[offset:]:
                if used + height > available:
                    break
                used += height
                count += 1
            return max(1, count)

        while True:
            if selected < scroll_offset:
                scroll_offset = selected
            while selected >= scroll_offset + count_visible(scroll_offset):
                scroll_offset += 1
            max_visible = count_visible(scroll_offset)

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
                                       show_index, show_counter,
                                       icons[visible_start:visible_end] if icons else None, compact)

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
                              show_index=True, show_counter=True, icons=None, compact=False):
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
        self.display.draw_list(title, items, cursor_pos, current_num, total_num,
                               first_visible_num, can_scroll_up, can_scroll_down,
                               show_index, show_counter, icons=icons, compact=compact)
