"""Classic terminal views and widgets shared by the recovery console."""

import curses
import fcntl
from functools import lru_cache
import os
import sys
import time
import unicodedata

from translations import t

_ACTIVE = None
_PAINT_CACHE = None
_HEADER = ('jrescue', '')
_HEADER_PROVIDER = None
_HEADER_CHECKED = 0
ENTER = (10, 13, curses.KEY_ENTER, '\n', '\r')
BACK = (27, '\x1b', 'q', 'Q')
# Use the fixed 256-color cube/grayscale rather than the themeable ANSI slots.
PALETTE_RGB = {
    'navy': (0, 0, 135), 'panel': (188, 188, 188), 'text': (0, 0, 0),
    'white': (255, 255, 255), 'cyan': (0, 255, 255), 'warning': (135, 0, 0),
    'inactive': (138, 138, 138), 'inactive_selection': (88, 88, 88),
}
_PALETTE_INDEX = {'navy': 18, 'panel': 250, 'text': 16, 'white': 231,
                  'cyan': 51, 'warning': 88, 'inactive': 245, 'inactive_selection': 240}


def clean(text):
    """Prevent data such as an SSID from injecting terminal controls."""
    text = str(text)
    if text.isascii() and text.isprintable():
        return text
    return ''.join('?' if unicodedata.category(c).startswith('C') else c
                   for c in text)


@lru_cache(maxsize=1024)
def _character_width(character):
    """Measure a cleaned glyph once; never cache complete input strings."""
    if unicodedata.combining(character):
        return 0
    return 2 if unicodedata.east_asian_width(character) in ('W', 'F') else 1


def cell_width(text):
    """Count terminal cells, including combining and wide Unicode characters."""
    text = clean(text)
    return len(text) if text.isascii() else sum(_character_width(c) for c in text)


def fit(text, width):
    """Clip to complete terminal cells without splitting a wide character."""
    text = clean(text)
    width = max(0, width)
    if text.isascii():
        return text[:width]
    result, used = '', 0
    for c in text:
        size = _character_width(c)
        if used + size > width:
            break
        if size == 0 and not result:
            continue
        result += c
        used += size
    return result


def wrap(text, width):
    """Wrap reports at spaces, retaining complete long SSIDs and addresses."""
    width = max(1, width)
    result = []
    for paragraph in str(text).expandtabs(4).split('\n'):
        remaining = clean(paragraph)
        if not remaining:
            result.append('')
        while remaining:
            line = fit(remaining, width)
            if not line:
                # A single wide glyph cannot fit a one-column terminal.
                result.append('?')
                remaining = remaining[1:]
                continue
            take = len(line)
            if take < len(remaining) and ' ' in line:
                split = line.rfind(' ')
                if split > 0:
                    take = split + 1
                    line = line[:split]
            result.append(line)
            remaining = remaining[take:]
    return result


def configure_header(title, provider=None):
    """Install a cached, read-only header provider; never query NM while painting."""
    global _HEADER, _HEADER_PROVIDER, _HEADER_CHECKED
    _HEADER, _HEADER_PROVIDER, _HEADER_CHECKED = (clean(title), ''), provider, 0


def header():
    """Refresh inexpensive kernel address data at most once every two seconds."""
    global _HEADER, _HEADER_CHECKED
    now = time.monotonic()
    if _HEADER_PROVIDER and now - _HEADER_CHECKED >= 2:
        _HEADER_CHECKED = now
        try:
            _HEADER = (_HEADER[0], clean(_HEADER_PROVIDER()))
        except (OSError, ValueError):
            _HEADER = (_HEADER[0], '')
    return _HEADER


def configure_terminal():
    """Correct the recovery service's Linux-VT default on serial/PTY terminals."""
    if os.environ.get('TERM') != 'linux':
        return
    try:
        descriptor = sys.stdin.fileno()
        if not os.isatty(descriptor):
            return
        try:
            # KDGETMODE succeeds only on a real Linux VT. /dev/console may
            # also refer to UART, so its filename cannot distinguish the two.
            fcntl.ioctl(descriptor, 0x4B3B, b'\0' * 4)
        except OSError:
            pass
        else:
            return
        # The recovery image includes this entry. Older images can keep linux.
        curses.setupterm(term='xterm-256color', fd=sys.stdout.fileno())
        if curses.tigetnum('colors') >= 256:
            os.environ['TERM'] = 'xterm-256color'
    except (AttributeError, OSError, ValueError, curses.error):
        pass


def init_colors():
    """Match the Classic preview without changing the terminal's own palette."""
    if not curses.has_colors():
        return
    curses.start_color()
    if curses.COLORS >= 256:
        colors = _PALETTE_INDEX
    else:
        colors = {'navy': curses.COLOR_BLUE, 'panel': curses.COLOR_WHITE,
                  'text': curses.COLOR_BLACK, 'warning': curses.COLOR_RED,
                  'white': 15 if curses.COLORS >= 16 else curses.COLOR_WHITE,
                  'cyan': 14 if curses.COLORS >= 16 else curses.COLOR_WHITE,
                  'inactive': 8 if curses.COLORS >= 16 else curses.COLOR_WHITE,
                  'inactive_selection': 8 if curses.COLORS >= 16 else curses.COLOR_BLUE}
    for index, fg, bg in ((1, colors['white'], colors['navy']),
                          (2, colors['navy'], colors['panel']),
                          (3, colors['text'], colors['panel']),
                          (4, colors['cyan'], colors['navy']),
                          (5, colors['text'], colors['white']),
                          (6, colors['warning'], colors['panel']),
                          (7, colors['text'], colors['text']),
                          (8, colors['text'], colors['inactive']),
                          (9, colors['navy'], colors['inactive']),
                          (10, colors['white'], colors['inactive_selection']),
                          (11, colors['warning'], colors['inactive'])):
        curses.init_pair(index, fg, bg)


def attribute(role):
    """Keep selected rows visible when colors or UTF-8 are unavailable."""
    if not curses.has_colors():
        return curses.A_REVERSE if role in ('selected', 'inactive_selected', 'field') else curses.A_NORMAL
    result = curses.color_pair({'background': 4, 'body': 3, 'accent': 2,
                                'selected': 1, 'warning': 6, 'field': 5, 'shadow': 7,
                                'inactive_body': 8, 'inactive_accent': 9,
                                'inactive_selected': 10, 'inactive_warning': 11}[role])
    # Eight-color terminals cannot distinguish white input from the gray panel.
    return result | curses.A_REVERSE if role == 'field' and curses.COLORS < 16 else result


class Frame:
    """A terminal-cell canvas used by curses and by local PNG previews."""
    def __init__(self, rows, cols, title, hint='', main=False, chrome=None, ascii_only=None,
                 dialog_size=None, backdrop=None):
        if ascii_only is None:
            ascii_only = os.environ.get('JRESCUE_TUI_ASCII') == '1'
        self.rows, self.cols = max(1, rows), max(1, cols)
        if (backdrop is not None and len(backdrop) == self.rows and
                all(len(row) == self.cols for row in backdrop)):
            self.cells = [row[:] for row in backdrop]
        else:
            self.cells = [[(' ', 'background')] * self.cols for _ in range(self.rows)]
        self.cursor = None
        self.ascii = ascii_only
        self.box_w = max(1, cols - (5 if cols >= 40 else 2))
        self.box_h = max(1, rows - (4 if rows >= 12 else 2))
        if dialog_size is not None:
            self.box_w = min(self.box_w, dialog_size[0])
            self.box_h = min(self.box_h, dialog_size[1])
        self.left, self.top = (cols - self.box_w) // 2, (rows - self.box_h) // 2
        self.x, self.y = self.left + 3, self.top + 2
        self.width, self.height = max(0, self.box_w - 6), max(0, self.box_h - 4)
        if rows < 8 or cols < 24:
            self.x, self.y, self.width, self.height = 0, 1, self.cols, max(0, rows - 2)
        else:
            if rows >= 12 and cols >= 40:
                self.put(self.left + 2, self.top + self.box_h, ' ' * self.box_w, 'shadow')
                for y in range(self.top + 1, self.top + self.box_h):
                    self.put(self.left + self.box_w, y, '  ', 'shadow')
            for y in range(self.top, min(rows, self.top + self.box_h)):
                self.put(self.left, y, ' ' * self.box_w, 'body')
            line = '-' if ascii_only else '─'
            corners = '++++||' if ascii_only else '┌┐└┘││'
            self.put(self.left, self.top, corners[0]+line * (self.box_w - 2)+corners[1], 'body')
            self.put(self.left, self.top + self.box_h - 1, corners[2]+line * (self.box_w - 2)+corners[3], 'body')
            for y in range(self.top + 1, self.top + self.box_h - 1):
                self.put(self.left, y, corners[4], 'body')
                self.put(self.left + self.box_w - 1, y, corners[5], 'body')
            caption = ' ' + fit(title, max(0, self.box_w - (6 if dialog_size else 20))) + ' '
            self.put(self.left + (self.box_w - cell_width(caption)) // 2, self.top, caption, 'accent')
        left, right = chrome if chrome is not None else header()
        right = fit(right, max(0, cols // 2 - 2))
        left = fit(' ' + left, max(0, cols - cell_width(right)-3))
        self.put(0, 0, left)
        if right:
            self.put(max(0, cols - cell_width(right)-1), 0, right)
        if dialog_size is not None:
            self.put(0, rows - 1, ' ' * self.cols)
        self.put(1, rows - 1, fit(hint, cols - 2))

    def put(self, x, y, text, role='background', width=None):
        if not 0 <= y < self.rows or x >= self.cols:
            return
        available = max(0, self.cols - max(0, x))
        text = fit(text, min(available, width) if width is not None else available)
        if width is not None:
            text += ' ' * max(0, min(width, available)-cell_width(text))
        # Dialog backgrounds and borders are mostly spaces/ASCII. Filling their
        # cells directly avoids Unicode work proportional to the whole terminal.
        if text.isascii():
            start, stop = max(0, x), min(self.cols, x + len(text))
            if stop > start:
                visible = text[start - x:stop - x]
                self.cells[y][start:stop] = ([(' ', role)] * len(visible) if not visible.strip(' ')
                                           else [(c, role) for c in visible])
            return
        column = x
        for c in text:
            n = _character_width(c)
            if n == 0:
                if column > max(0, x):
                    previous, old_role = self.cells[y][column - 1]
                    self.cells[y][column - 1] = (previous + c, old_role)
                continue
            if 0 <= column < self.cols:
                self.cells[y][column] = (c, role)
                for tail in range(1, n):
                    if column + tail < self.cols:
                        self.cells[y][column + tail] = ('', role)
            column += n

    def write(self, row, text, role='body', indent=0, selected=False):
        if 0 <= row < self.height:
            self.put(self.x + indent, self.y + row, text, 'selected' if selected else role,
                     self.width - indent if selected else min(self.width - indent, cell_width(text)))

    def counter(self, current, total):
        text = ' {}/{} '.format(current, total)
        if self.box_w > cell_width(text)+12:
            self.put(self.left + self.box_w - cell_width(text)-2, self.top, text, 'accent')

    def paint(self, window, refresh=True):
        """Paint only on the UI thread; a resize never accepts a hidden action."""
        global _PAINT_CACHE
        if window.getmaxyx() != (self.rows, self.cols):
            _PAINT_CACHE = None
            return False
        encoding = getattr(window, 'encoding', 'utf-8') or 'utf-8'
        target = (self.rows, self.cols, str(encoding).lower())
        previous = None
        if (refresh and _PAINT_CACHE is not None and
                _PAINT_CACHE[0] is window and _PAINT_CACHE[1] == target):
            previous = _PAINT_CACHE[2]
        # A failed paint or a base frame followed by external progress drawing
        # must force a complete redraw next time.
        _PAINT_CACHE = None
        if previous is None:
            window.erase()
        for y, row in enumerate(self.cells):
            if previous is not None and row == previous[y]:
                continue
            x = 0
            while x < self.cols:
                role, start, text = row[x][1], x, ''
                while x < self.cols and row[x][1] == role:
                    text += row[x][0]
                    x += 1
                try:
                    if 'utf' not in target[2]:
                        text = text.translate(str.maketrans({'┌': '+', '┐': '+', '└': '+', '┘': '+', '│': '|', '─': '-'}))
                        text = text.encode(encoding, errors='replace').decode(encoding)
                        text += ' ' * max(0, x - start - cell_width(text))
                    window.addstr(y, start, text, attribute(role))
                except curses.error:
                    if y != self.rows - 1 or x != self.cols:
                        raise
        try:
            curses.curs_set(1 if self.cursor else 0)
            if self.cursor:
                window.move(*self.cursor)
        except curses.error:
            pass
        if refresh:
            window.refresh()
            _PAINT_CACHE = (window, target, [row[:] for row in self.cells])
        return True


def new_frame(window, title, hint='', main=False):
    """Use current terminal dimensions on every redraw, including KEY_RESIZE."""
    rows, cols = window.getmaxyx()
    encoding = getattr(window, 'encoding', 'utf-8')
    ascii_only = os.environ.get('JRESCUE_TUI_ASCII') == '1' or 'utf' not in str(encoding).lower()
    return Frame(rows, cols, title, hint, main, ascii_only=ascii_only)


def run(callback, *args, **kwargs):
    """Reuse one curses session instead of resetting the terminal between screens."""
    global _PAINT_CACHE
    if _ACTIVE is not None:
        _ACTIVE.timeout(-1)
        return callback(_ACTIVE, *args, **kwargs)
    configure_terminal()
    _PAINT_CACHE = None
    try:
        return curses.wrapper(callback, *args, **kwargs)
    finally:
        _PAINT_CACHE = None


def session(callback):
    """Keep terminal setup outside all network/download/write workers."""
    configure_terminal()
    def start(window):
        global _ACTIVE, _PAINT_CACHE
        _PAINT_CACHE = None
        init_colors()
        window.keypad(True)
        _ACTIVE = window
        try:
            return callback()
        finally:
            _ACTIVE = None
            _PAINT_CACHE = None
    return curses.wrapper(start)


def key(window, timed=False):
    """Read Unicode input and turn curses timeout exceptions into refresh ticks."""
    try:
        return window.get_wch()
    except curses.error:
        if timed:
            return None
        raise


def back(value):
    return value in BACK


def help_screen(window):
    """Short keyboard help stays available without leaving the current screen."""
    text_screen(window, t('tui_help'), t('tui_help_body').split('\n'), allow_help=False)


def center_content(frame, width):
    """Center one content block while keeping its rows and columns left-aligned."""
    width = min(frame.width, max(0, width))
    frame.x += (frame.width - width) // 2
    frame.width = width
    return frame


def content_width(lines, minimum=28):
    """Measure natural text width; the frame still limits it to the terminal."""
    return max(minimum, max((cell_width(part) for line in lines
                             for part in str(line).split('\n')), default=0))


def _table_width(columns, data, details=None):
    """Use the same column sizes when centering standalone and tabbed tables."""
    widths = [max([cell_width(str(row[i])) for row in data] + [cell_width(label)])
              for i, label in enumerate(columns)]
    widths[1:] = [max(8, min(12, width)) for width in widths[1:]]
    return max(32, sum(widths) + 2 * len(columns), content_width(details or [], 0))


def menu_frame(rows, cols, title, options, selected=0, main=False, chrome=None):
    """Keep the parent expanding and center each menu's description and list."""
    f = Frame(rows, cols, title, t('tui_hint_menu'), main, chrome=chrome)
    natural = content_width(options, 0) + (13 if main else len(str(len(options))) + 5)
    center_content(f, max(28, natural, cell_width(t('tui_restore')) if main else 0))
    offset = (4 if f.height >= 14 else 2 if f.height >= 10 else 0) if main else 0
    if offset:
        f.write(0, t('tui_restore'))
    if offset >= 4:
        f.write(2, ('-' if f.ascii else '─') * f.width)
    step = 2 if f.height - offset >= min(4, len(options))*2 else 1
    visible = max(1, (f.height - offset) // step)
    top = max(0, min(selected - visible + 1, max(0, len(options)-visible)))
    for i, option in enumerate(options[top:top + visible]):
        index = top + i
        text = '{} {}  {}{}'.format('>' if index == selected else ' ', index + 1, option,
                                    '  --->' if main else '')
        f.write(offset + i * step, text, selected=index == selected)
    if options:
        f.counter(selected + 1, len(options))
    return f


def menu(window, title, options, title_fn=None, refresh_ms=2000, main=False, initial_index=0):
    """Return a one-based selection or zero on Back; resize preserves selection."""
    init_colors()
    selected = min(max(0, initial_index), max(0, len(options)-1))
    heading = title
    window.timeout(refresh_ms if title_fn else 1000)
    while True:
        f = menu_frame(*window.getmaxyx(), heading, options, selected, main)
        if not f.paint(window):
            continue
        window.timeout(refresh_ms if title_fn else 1000)
        value = key(window, timed=True)
        if value is None:
            if title_fn:
                heading = title_fn()
            continue
        if back(value):
            return 0
        if value == curses.KEY_F1:
            help_screen(window)
        elif value in (curses.KEY_UP, curses.KEY_PPAGE):
            selected = max(0, selected - (max(1, f.height // 2) if value == curses.KEY_PPAGE else 1))
        elif value in (curses.KEY_DOWN, curses.KEY_NPAGE):
            selected = min(len(options)-1, selected + (max(1, f.height // 2) if value == curses.KEY_NPAGE else 1))
        elif value in ENTER and options and f.height > 0:
            return selected + 1
        elif isinstance(value, str) and value in '123456789':
            selected = min(int(value)-1, len(options)-1)


def text_frame(rows, cols, title, lines, top=0, hint=None, chrome=None):
    """Wrap reports before scrolling so long addresses are never silently clipped."""
    f = Frame(rows, cols, title, hint or t('tui_hint_text'), chrome=chrome)
    center_content(f, content_width(lines))
    content = [part for line in lines for part in wrap(line, f.width)]
    maximum = max(0, len(content)-f.height)
    top = max(0, min(top, maximum))
    for row, text in enumerate(content[top:top + f.height]):
        f.write(row, text)
    if maximum:
        f.counter(top + 1, max(1, len(content)))
    return f, maximum


def text_screen(window, title, lines, refresh_fn=None, refresh_ms=2000, allow_help=True):
    """Show passive text; Enter closes it and never starts an operation."""
    init_colors()
    top = 0
    window.timeout(refresh_ms if refresh_fn else - 1)
    while True:
        f, maximum = text_frame(*window.getmaxyx(), title, lines, top)
        if not f.paint(window):
            continue
        window.timeout(refresh_ms if refresh_fn else - 1)
        value = key(window, timed=bool(refresh_fn))
        if value is None:
            if refresh_fn:
                lines = refresh_fn()
            continue
        if value in ENTER or back(value):
            return
        if value == curses.KEY_F1 and allow_help:
            help_screen(window)
        elif value in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            step = f.height if value in (curses.KEY_PPAGE, curses.KEY_NPAGE) else 1
            top += -step if value in (curses.KEY_UP, curses.KEY_PPAGE) else step
            top = max(0, min(top, maximum))
        elif value == curses.KEY_HOME:
            top = 0
        elif value == curses.KEY_END:
            top = maximum


def choice_frame(rows, cols, title, lines, choices, selected=0, chrome=None):
    """Show explanatory text and explicit, localized buttons."""
    f = Frame(rows, cols, title, t('tui_hint_choice'), chrome=chrome)
    buttons = ['< ' + label + ' >' for label in choices]
    buttons_width = sum(map(cell_width, buttons)) + 3 * (len(buttons) - 1)
    center_content(f, max(content_width(lines), buttons_width))
    content = [part for line in lines for part in wrap(line, f.width)]
    minimum = len(content)+2
    fits = minimum <= f.height and sum(map(cell_width, buttons))+3 * (len(buttons)-1) <= f.width
    if not fits:
        f.write(0, t('tui_resize'), 'warning')
        return f, False
    for row, line in enumerate(content):
        f.write(row, line)
    x = (f.width - buttons_width) // 2
    for i, button in enumerate(buttons):
        f.put(f.x + x, f.y + len(content)+1, button, 'selected' if i == selected else 'body')
        x += cell_width(button)+3
    return f, True


def horizontal_menu(window, title, options, lines=None):
    """The first button is the safe default; an opening Enter cannot confirm YES."""
    init_colors()
    window.timeout(-1)
    selected = 0
    while True:
        f, fits = choice_frame(*window.getmaxyx(), title if lines is not None else t('confirm_title'),
                               lines if lines is not None else [title], options, selected)
        if not f.paint(window):
            continue
        value = key(window)
        if back(value):
            return 0
        if value == curses.KEY_F1:
            help_screen(window)
        elif value in (curses.KEY_LEFT, curses.KEY_UP):
            selected = max(0, selected - 1)
        elif value in (curses.KEY_RIGHT, curses.KEY_DOWN, '\t'):
            selected = (selected + 1) % len(options)
        elif value in ENTER and fits:
            return selected + 1


def _dialog_frame(rows, cols, title, size, hint, background=None, chrome=None):
    """Keep modal geometry independent of the expanding parent screen."""
    if callable(background):
        background = background(rows, cols)
    if isinstance(background, Frame):
        background = background.cells
    if (background is None or len(background) != rows or
            any(len(row) != cols for row in background)):
        background = Frame(rows, cols, '', chrome=chrome).cells
    # Change a copy so closing the dialog restores the parent's original colors.
    roles = {'body': 'inactive_body', 'accent': 'inactive_accent',
             'selected': 'inactive_selected', 'warning': 'inactive_warning', 'field': 'inactive_body'}
    dimmed = [[(char, roles.get(role, role)) for char, role in row] for row in background]
    return Frame(rows, cols, title, hint, chrome=chrome, dialog_size=size, backdrop=dimmed)


def _current_background(window):
    """Capture the parent before any modal replaces the paint snapshot."""
    if (_PAINT_CACHE is not None and _PAINT_CACHE[0] is window and
            _PAINT_CACHE[1][:2] == window.getmaxyx()):
        return _PAINT_CACHE[2]
    return None


def _dialog_buttons(frame, row, selected):
    """Use the same centered OK/Cancel buttons in all compact dialogs."""
    labels = ['< ' + t('ok') + ' >', '< ' + t('cancel') + ' >']
    width = sum(cell_width(label) for label in labels) + 4
    if row >= frame.height or width > frame.width:
        return False
    x = frame.x + (frame.width - width) // 2
    for index, label in enumerate(labels):
        frame.put(x, frame.y + row, label, 'selected' if selected == index else 'body')
        x += cell_width(label) + 4
    return True


def compact_confirmation_frame(rows, cols, title, lines, selected=1, size=(64, 11),
                               background=None, chrome=None):
    """Approve only when the entire warning and both buttons are visible."""
    frame = _dialog_frame(rows, cols, title, size, t('tui_hint_choice'), background, chrome)
    content = [(part, 'warning' if index == 0 else 'body')
               for index, line in enumerate(lines) for part in wrap(line, frame.width)]
    fits = len(content) + 2 <= frame.height
    if fits:
        for row, (text, role) in enumerate(content):
            frame.write(row, text, role)
        fits = _dialog_buttons(frame, len(content) + 1, selected)
    if not fits:
        frame.write(0, t('tui_resize'), 'warning')
    return frame, fits


def compact_confirmation(window, title, lines, size=(64, 11)):
    """Cancel is the default, including after a resize hides the warning."""
    init_colors()
    window.timeout(-1)
    background = _current_background(window)
    selected = 1
    while True:
        frame, fits = compact_confirmation_frame(*window.getmaxyx(), title, lines, selected,
                                                size, background)
        if not frame.paint(window):
            continue
        if not fits:
            selected = 1
        pressed = key(window)
        if back(pressed):
            return False
        if pressed == curses.KEY_F1:
            help_screen(window)
        elif not fits:
            continue
        elif pressed in (curses.KEY_LEFT, curses.KEY_UP):
            selected = 0
        elif pressed in (curses.KEY_RIGHT, curses.KEY_DOWN):
            selected = 1
        elif pressed in ('\t', curses.KEY_BTAB):
            selected = 1 - selected
        elif pressed in ENTER:
            return selected == 0


def input_frame(rows, cols, title, prompt, value, cursor, password=False, chrome=None,
                selected=0, background=None):
    """Render a scrollable insertion cursor and a masked password field."""
    f = (_dialog_frame(rows, cols, title, (56, 11), t('tui_hint_password'), background, chrome)
         if password else Frame(rows, cols, title, t('tui_hint_input'), chrome=chrome))
    if not password:
        center_content(f, content_width([prompt], 60))
    prompt_lines = wrap(prompt, f.width)
    field_row = len(prompt_lines)+2
    fits = (field_row + 3 <= f.height if password else field_row + 2 < f.height) and f.width >= 12
    if not fits:
        f.write(0, t('tui_resize'), 'warning')
        return f, False
    for row, line in enumerate(prompt_lines):
        f.write(row, line, 'accent')
    if password:
        f.write(field_row - 1, t('tui_password_label'))
    shown = '*' * len(value) if password else value
    position = min(cursor, len(shown))
    start = 0
    available = f.width - 4
    while cell_width(shown[start:position]) >= available:
        start += 1
    tail = fit(shown[start:], available)
    f.write(field_row, '[ ' + tail + ' ' * max(0, available - cell_width(tail))+' ]',
            'field' if password else 'body')
    if not password or selected == 0:
        f.cursor = (f.y + field_row, f.x + 2 + cell_width(shown[start:position]))
    if password:
        fits = _dialog_buttons(f, field_row + 2, selected)
        if not fits:
            f.write(0, t('tui_resize'), 'warning')
    return f, fits


def input_dialog(window, title, prompt, password=False, initial='', background=None):
    """Edit at the cursor, preserving spaces and hidden suffixes."""
    init_colors()
    window.timeout(-1)
    value, cursor = initial, len(initial)
    selected = 0
    if background is None:
        background = _current_background(window)
    while True:
        f, fits = input_frame(*window.getmaxyx(), title, prompt, value, cursor, password,
                              selected=selected, background=background)
        if not f.paint(window):
            continue
        if password and not fits:
            selected = 1
        pressed = key(window)
        if pressed in (27, '\x1b'):
            return None
        if pressed == curses.KEY_F1:
            help_screen(window)
        elif not fits:
            continue
        elif password and pressed in ('\t', curses.KEY_BTAB):
            selected = 1 - selected
        elif pressed in ENTER and fits:
            return None if password and selected == 1 else value
        elif password and selected == 1 and pressed in (
                curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_UP, curses.KEY_DOWN):
            selected = int(pressed in (curses.KEY_RIGHT, curses.KEY_DOWN))
        elif pressed == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
        elif pressed == curses.KEY_RIGHT:
            cursor = min(len(value), cursor + 1)
        elif pressed == curses.KEY_HOME:
            selected = 0
            cursor = 0
        elif pressed == curses.KEY_END:
            selected = 0
            cursor = len(value)
        elif pressed in (curses.KEY_BACKSPACE, '\x7f', '\b') and cursor:
            selected = 0
            value = value[:cursor - 1]+value[cursor:]
            cursor -= 1
        elif pressed == curses.KEY_DC:
            selected = 0
            value = value[:cursor]+value[cursor + 1:]
        elif isinstance(pressed, str) and pressed.isprintable():
            selected = 0
            value = value[:cursor]+pressed + value[cursor:]
            cursor += len(pressed)


def _action_body(f, lines, token, entered=''):
    """Share warning visibility and token geometry across dialogs and tabs."""
    content = [part for line in lines for part in wrap(line, f.width)]
    prompt = wrap(t('tui_type_token', token=token), f.width)
    fits = len(content)+len(prompt)+3 <= f.height and f.width >= len(token)+4
    if not fits:
        f.write(0, t('tui_resize'), 'warning')
        return False
    for row, line in enumerate(content):
        f.write(row, line, 'warning' if row == 0 else 'body')
    for i, line in enumerate(prompt):
        f.write(len(content)+1 + i, line, 'accent')
    field_row = len(content)+len(prompt)+1
    f.write(field_row, '[ ' + entered + ' ]')
    f.cursor = (f.y + field_row, f.x + 2 + cell_width(entered))
    return True


def action_frame(rows, cols, title, lines, token, entered='', chrome=None):
    """A critical action needs its complete warning and an exact typed token."""
    f = Frame(rows, cols, title, t('tui_hint_confirm'), chrome=chrome)
    center_content(f, max(content_width(lines), cell_width(t('tui_type_token', token=token))))
    return f, _action_body(f, lines, token, entered)


def action_confirmation(window, title, lines, token):
    """Never accept a token hidden by a resize or entered through a failed UI."""
    init_colors()
    window.timeout(-1)
    entered = ''
    while True:
        f, fits = action_frame(*window.getmaxyx(), title, lines, token, entered)
        if not f.paint(window):
            continue
        pressed = key(window)
        if pressed in (27, '\x1b'):
            return False
        if not fits:
            entered = ''
            continue
        if pressed == curses.KEY_F1:
            help_screen(window)
        elif pressed in ENTER:
            if entered == token:
                return True
        elif pressed in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            entered = entered[:-1]
        elif isinstance(pressed, str) and pressed.isprintable() and len(entered) < len(token):
            entered += pressed


def _table_body(f, columns, data, selected=0, details=None):
    """Render the same list geometry in standalone dialogs and Network tabs."""
    center_content(f, _table_width(columns, data, details))
    widths = [max(8, min(12, max([cell_width(str(row[i])) for row in data]+[cell_width(label)])))
              for i, label in enumerate(columns)]
    widths[0] = max(4, f.width - sum(widths[1:])-2 * len(widths))
    def format_row(values):
        cells = [fit(str(value), widths[i]) for i, value in enumerate(values)]
        return '  '.join(value + ' ' * max(0, widths[i]-cell_width(value))
                         for i, value in enumerate(cells))
    f.write(0, '  ' + format_row(columns), 'accent')
    f.write(1, '-' * f.width, 'accent')
    extra = wrap(details[selected], f.width) if details and data else []
    reserved = min(len(extra)+2, max(0, f.height // 2)) if extra else 0
    visible = max(1, f.height - 2 - reserved)
    top = max(0, min(selected - visible + 1, max(0, len(data)-visible)))
    for i, values in enumerate(data[top:top + visible]):
        index = top + i
        f.write(2 + i, ('> ' if index == selected else '  ')+format_row(values), selected=index == selected)
    if extra:
        start = max(3, f.height - reserved)
        for i, line in enumerate(extra):
            f.write(start + i, line)
    if data:
        f.counter(selected + 1, len(data))
    return f


def table_frame(rows, cols, title, columns, data, selected=0, details=None, chrome=None):
    """Use spare terminal width for names and keep selected details complete."""
    f = Frame(rows, cols, title, t('tui_hint_menu'), chrome=chrome)
    return _table_body(f, columns, data, selected, details)


def table_menu(window, title, columns, data, details=None):
    """Return a one-based row selection; Esc cancels without choosing an image."""
    init_colors()
    window.timeout(-1)
    selected = 0
    while True:
        f = table_frame(*window.getmaxyx(), title, columns, data, selected, details)
        if not f.paint(window):
            continue
        pressed = key(window)
        if back(pressed):
            return 0
        if pressed == curses.KEY_F1:
            help_screen(window)
        elif pressed in (curses.KEY_UP, curses.KEY_PPAGE):
            selected = max(0, selected - (max(1, f.height - 4) if pressed == curses.KEY_PPAGE else 1))
        elif pressed in (curses.KEY_DOWN, curses.KEY_NPAGE):
            selected = min(len(data)-1, selected + (max(1, f.height - 4) if pressed == curses.KEY_NPAGE else 1))
        elif pressed in ENTER and data and f.height >= 4:
            return selected + 1


def network_fields(device, width):
    """Display local state and every IPv4/IPv6 address, with no Internet probes."""
    state = device.get('state')
    status = ('OK' if device.get('connected') else t('tui_state_' +
              ({10: 'unmanaged', 20: 'unavailable', 30: 'disconnected', 40: 'connecting', 50: 'connecting',
                60: 'auth', 70: 'connecting', 80: 'connecting', 90: 'connecting', 110: 'disconnecting', 120: 'failed'}.get(state, 'unknown'))))
    lines = [device.get('interface', '--')+' / ' + ('WiFi' if device.get('kind') == 'wifi' else 'Ethernet'),
             t('tui_status')+': ' + status]
    if device.get('kind') == 'wifi':
        lines.append('SSID: ' + (device.get('ssid') or '--'))
    addresses = device.get('addresses') or ([device['ip']] if device.get('ip') else [])
    if not addresses:
        lines.append('IP: --')
    for address in addresses:
        lines.append(('IPv6: ' if ':' in address else 'IPv4: ')+address)
    return [part for line in lines for part in wrap(line, width)]


NETWORK_TABS = ('status', 'wifi', 'restart')


def wifi_rows(networks):
    """Keep standalone and tabbed WiFi lists consistent."""
    data = []
    for network in networks:
        try:
            strength = max(0, min(100, int(network.get('signal', 0))))
        except (ValueError, TypeError):
            strength = 0
        security = (network.get('security') or '').strip()
        data.append((network['ssid'], security if security.upper() not in ('', '--', 'OPEN')
                     else t('tui_open_network'), str(strength) + '%'))
    return data


def _network_tabs(f, selected):
    """Draw tabs at the parent header even after its content geometry moved."""
    y = f.top + 2
    labels = (t('tui_status'), t('tui_wifi'), t('tui_restart'))
    group_width = sum(cell_width(label) + 4 for label in labels) - 2
    horizontal = group_width <= f.width
    x = (f.width - group_width) // 2 if horizontal else 0
    start = 2 if horizontal else 4
    for i, label in enumerate(labels):
        text = ' ' + label + ' '
        if horizontal:
            f.put(f.x + x, y, text, 'selected' if i == selected else 'body', min(cell_width(text), max(0, f.width - x)))
            x += cell_width(text)+2
        else:
            f.put(f.x, y + i, text, 'selected' if i == selected else 'body', f.width)
    return start


def _restart_lines():
    """Explain the action before Enter opens the separate confirmation dialog."""
    return [(t('tui_restart_service'), 'body'),
            (t('tui_restart_restore'), 'body'), ('', 'body'),
            (t('tui_restart_warning'), 'warning'), ('', 'body'),
            (t('tui_restart_profiles'), 'body'), ('', 'body'),
            (t('tui_restart_enter'), 'accent')]


def network_frame(rows, cols, devices, selected=0, top=0, chrome=None,
                  networks=None, error_lines=None, wifi_index=0, entered='', notice=None,
                  confirm_selected=1, restart_confirm=False):
    """Draw a tab or its compact restart dialog without changing networking."""
    if selected == 2 and restart_confirm:
        background, _ = network_frame(rows, cols, devices, selected=2, chrome=chrome)
        f, fits = compact_confirmation_frame(
            rows, cols, t('tui_restart_confirm'),
            [t('tui_restart_warning'), '', t('tui_restart_profiles')],
            confirm_selected, background=background, chrome=chrome)
        f.choice_fits = fits
        return f, 0
    f = Frame(rows, cols, t('tui_network'), t('tui_network_tabs'), chrome=chrome)
    tabs_width = sum(cell_width(label) + 4 for label in
                     (t('tui_status'), t('tui_wifi'), t('tui_restart'))) - 2
    status_widths = [content_width(network_fields(device, 10000), 0) for device in devices]
    wide = len(devices) == 2 and sum(status_widths) + 4 <= f.width
    if selected == 1:
        details = ['SSID: ' + item['ssid'] + '\n' + (item.get('security') or '')
                   for item in networks or []]
        page_width = max(_table_width(['SSID', t('tui_security'), t('tui_signal')],
                                      wifi_rows(networks or []), details),
                         content_width(error_lines or [], 0),
                         content_width([notice] if notice else [], 0))
    elif selected == 2:
        page_width = content_width([line for line, _ in _restart_lines()])
    else:
        page_width = sum(status_widths) + 4 if wide else max(status_widths, default=28)
    center_content(f, max(tabs_width, page_width))
    start = _network_tabs(f, selected)
    f.y += start
    f.height = max(0, f.height - start)
    if selected == 2:
        content = [(part, role) for line, role in _restart_lines() for part in wrap(line, f.width)]
        maximum = max(0, len(content) - f.height)
        top = max(0, min(top, maximum))
        for row, (line, role) in enumerate(content[top:top + f.height]):
            f.write(row, line, role)
        return f, maximum
    if selected == 1:
        if error_lines or not networks:
            content = error_lines or [t('no_networks'), t('make_sure_wifi')]
            parts = [part for line in content for part in wrap(line, f.width)]
            for row, line in enumerate(parts):
                f.write(row, line)
            return f, 0
        if notice:
            parts = wrap(notice, f.width)
            for row, line in enumerate(parts):
                f.write(row, line)
            f.y += len(parts) + 1
            f.height = max(0, f.height - len(parts) - 1)
        data = wifi_rows(networks)
        details = ['SSID: ' + row[0] + '\n' + row[1] for row in data]
        _table_body(f, ['SSID', t('tui_security'), t('tui_signal')], data, wifi_index, details)
        return f, 0
    capacity = f.height
    if wide:
        parts = [network_fields(device, width) for device, width in zip(devices, status_widths)]
        maximum = max(0, max(map(len, parts), default=0)-capacity)
        top = max(0, min(top, maximum))
        indent = (f.width - sum(status_widths) - 4) // 2
        for column, content in enumerate(parts):
            for row, line in enumerate(content[top:top + capacity]):
                f.write(row, line, 'accent' if row == 0 and top == 0 else 'body', indent=indent)
            indent += status_widths[column] + 4
    else:
        content = []
        for device in devices:
            content += network_fields(device, f.width)+['']
        if not devices:
            content = [t('tui_no_interfaces')]
        maximum = max(0, len(content)-capacity)
        top = max(0, min(top, maximum))
        for row, line in enumerate(content[top:top + capacity]):
            f.write(row, line)
    return f, maximum


def network_screen(window, devices, tab='status', networks=None, error_lines=None,
                   wifi_index=0, notice=None, return_tab='status'):
    """Arrows browse tabs; Enter opens restart confirmation before explicit OK."""
    init_colors()
    window.timeout(-1)
    selected, top, confirmation = NETWORK_TABS.index(tab), 0, 1
    restart_confirm = False
    cancel_tab = NETWORK_TABS.index(return_tab if return_tab in ('status', 'wifi') else 'status')
    wifi_index = max(0, min(wifi_index, len(networks or []) - 1))
    def result(action, tab_index=selected):
        return {'action': action, 'tab': NETWORK_TABS[tab_index], 'wifi_index': wifi_index}
    while True:
        f, maximum = network_frame(*window.getmaxyx(), devices, selected, top,
                                  networks=networks, error_lines=error_lines, wifi_index=wifi_index,
                                  notice=notice, confirm_selected=confirmation,
                                  restart_confirm=restart_confirm)
        if not f.paint(window):
            continue
        if restart_confirm and not f.choice_fits:
            confirmation = 1
        pressed = key(window)
        if restart_confirm:
            if back(pressed):
                return result('tab', cancel_tab)
            if pressed == curses.KEY_F1:
                help_screen(window)
            elif not f.choice_fits:
                continue
            elif pressed in (curses.KEY_LEFT, curses.KEY_UP):
                confirmation = 0
            elif pressed in (curses.KEY_RIGHT, curses.KEY_DOWN):
                confirmation = 1
            elif pressed in ('\t', curses.KEY_BTAB):
                confirmation = 1 - confirmation
            elif pressed in ENTER:
                return result('restart') if confirmation == 0 else result('tab', cancel_tab)
            continue
        if back(pressed):
            return None
        if pressed in ('\t', curses.KEY_RIGHT):
            return result('tab', (selected + 1) % 3)
        elif pressed == curses.KEY_LEFT:
            return result('tab', (selected - 1) % 3)
        elif pressed == curses.KEY_F1:
            help_screen(window)
        elif pressed in ('r', 'R'):
            return result('refresh')
        elif pressed in ENTER and f.height >= 3:
            if selected == 0:
                return result('refresh')
            if selected == 2:
                restart_confirm = True
                confirmation = 1
            elif networks and not error_lines:
                return result('connect')
        elif pressed in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            step = max(1, f.height - 3) if pressed in (curses.KEY_PPAGE, curses.KEY_NPAGE) else 1
            direction = -1 if pressed in (curses.KEY_UP, curses.KEY_PPAGE) else 1
            if selected == 1:
                wifi_index = max(0, min(max(0, len(networks or []) - 1), wifi_index + direction * step))
            else:
                top = max(0, min(maximum, top + direction * step))


def operation_frame(rows, cols, title, lines, percent=None, frame=0, cancelable=False,
                    cancelling=False, chrome=None):
    """Draw bounded progress on the UI thread, never from its worker callback."""
    hint = t('hint_download_cancel') if cancelable else t('tui_write_busy') if percent is not None else t('tui_wait')
    f = Frame(rows, cols, t('download_cancelling') if cancelling else title, hint, chrome=chrome)
    center_content(f, content_width(lines, 60))
    y = max(0, f.height // 2 - 2)
    if percent is None or cancelling:
        f.write(y, '|/-\\'[frame % 4]+' ' + t('tui_wait'), 'accent')
    else:
        width = max(1, f.width - 9)
        percent = min(100, max(0, percent))
        filled = round(width * percent / 100)
        f.write(y, '[' + '#' * filled + '-' * (width - filled)+'] ' + str(round(percent)).rjust(3)+'%', 'accent')
    row = y + 2
    for text in lines:
        for line in wrap(text, f.width):
            f.write(row, line)
            row += 1
    return f


def settings(window, title, items):
    """Retain the declarative runtime-settings API without inline plain input."""
    selected = 0
    while True:
        labels = []
        for item in items:
            label = item['label']() if callable(item['label']) else item['label']
            if item['type'] == 'bool':
                label = '[{}] {}'.format('x' if item['get']() else ' ', label)
            elif item['type'] == 'choice':
                label += ': ' + next((text for value, text in item['choices'] if value == item['get']()), '--')
            elif item['type'] in ('string', 'int'):
                label += ': ' + str(item['get']())
            labels.append(label)
        choice = menu(window, title, labels, initial_index=selected)
        if not choice:
            return None
        selected = choice - 1
        item = items[selected]
        kind = item['type']
        if kind == 'action':
            return item['action']
        if kind == 'bool':
            item['set'](not item['get']())
        elif kind == 'choice':
            choice = menu(window, labels[selected], [label for _, label in item['choices']])
            if choice:
                item['set'](item['choices'][choice - 1][0])
        else:
            value = input_dialog(window, labels[selected], item.get('help', ''), initial=str(item['get']()))
            if value is not None:
                try:
                    item['set'](int(value) if kind == 'int' else value)
                except ValueError:
                    text_screen(window, t('error'), [t('tui_invalid_value')])


def power_pending(window, title):
    """Keep shutdown feedback visible until systemd stops the console service."""
    init_colors()
    window.timeout(500)
    while True:
        f = Frame(*window.getmaxyx(), title, t('tui_wait'))
        center_content(f, content_width([title]))
        f.write(max(0, f.height // 2), title, 'accent')
        if f.paint(window):
            key(window, timed=True)
