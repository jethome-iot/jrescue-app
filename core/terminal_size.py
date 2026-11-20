"""Read serial terminal dimensions without treating size reports as key presses."""

from collections import deque
import curses
import fcntl
import os
import re
import struct
import sys
import termios
import time


class SerialResize:
    """Poll an xterm-compatible UART terminal on the curses UI thread."""

    def __init__(self, input_fd, output_fd, redraw):
        self.input_fd = input_fd
        self.output_fd = output_fd
        self.redraw = redraw
        self.next_query = 0
        self.query_until = 0
        self.prefix = ''
        self.prefix_until = 0
        self.discard_report = False
        self.queued = deque()

    def _query(self, now):
        if self.prefix.startswith('\x1b[8;') and now > self.prefix_until:
            self.discard_report = True
        if now < self.next_query or (self.prefix and not self.discard_report):
            return
        request = b'\x1b[18t'
        while request:
            written = os.write(self.output_fd, request)
            if written <= 0:
                raise OSError('Cannot query serial terminal size')
            request = request[written:]
        self.query_until = now + 2
        self.next_query = now + 1

    def _apply_report(self, window):
        match = re.fullmatch(r'\x1b\[8;([0-9]{1,3});([0-9]{1,3})t', self.prefix)
        if not match or self.discard_report:
            return None
        rows, cols = map(int, match.groups())
        if not (1 <= rows <= 256 and 1 <= cols <= 512):
            return None
        if (rows, cols) == window.getmaxyx():
            return None
        # UART has no SSH-like window-change channel. Update the local tty and
        # curses together only after receiving a complete, bounded size report.
        fcntl.ioctl(self.input_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        try:
            curses.resizeterm(rows, cols)
        except curses.error as exc:
            raise RuntimeError('Cannot resize the serial terminal') from exc
        self.redraw(window)
        return curses.KEY_RESIZE

    def _feed(self, value, window, now):
        if value in (curses.KEY_RESIZE, '\x0c', 12):
            return value
        if not self.prefix:
            if value == '\x1b' and now <= self.query_until:
                self.prefix = value
                self.prefix_until = now + 0.05
                return None
            return value
        if self.prefix.startswith('\x1b[8;'):
            if now > self.prefix_until:
                self.discard_report = True
            if isinstance(value, str) and len(value) == 1 and value in '0123456789;t':
                if len(self.prefix) < 24:
                    self.prefix += value
                else:
                    self.discard_report = True
                if value != 't':
                    return None
                try:
                    return self._apply_report(window)
                finally:
                    self.prefix, self.discard_report = '', False
            self.prefix, self.discard_report = '', False
            if value == '\x1b':
                self.prefix, self.prefix_until = '\x1b', now + 0.05
                return None
            # A broken/truncated report must never turn an Enter into approval.
            return curses.KEY_RESIZE if value in ('\n', '\r', 10, 13, curses.KEY_ENTER) else value
        expected = {'\x1b': '[', '\x1b[': '8', '\x1b[8': ';'}[self.prefix]
        if value == expected:
            self.prefix += value
            self.prefix_until = now + (2 if self.prefix == '\x1b[8;' else 0.05)
            return None
        self.queued.extend(self.prefix[1:])
        if value == '\x1b':
            self.prefix, self.prefix_until = '\x1b', now + 0.05
            return '\x1b'
        self.queued.append(value)
        self.prefix = ''
        return '\x1b'

    def read(self, window, timed=False, delay=-1):
        """Preserve caller deadlines, immediate arrows and ordinary Escape input."""
        deadline = time.monotonic() + delay / 1000 if delay >= 0 else None
        consumed = 0
        try:
            while True:
                now = time.monotonic()
                self._query(now)
                if self.queued:
                    return self.queued.popleft()
                if self.prefix and not self.prefix.startswith('\x1b[8;') and now >= self.prefix_until:
                    self.queued.extend(self.prefix[1:])
                    self.prefix = ''
                    return '\x1b'
                wait = 100 if deadline is None else max(0, min(100, int((deadline - now) * 1000)))
                if self.prefix and not self.prefix.startswith('\x1b[8;'):
                    wait = min(wait, max(1, int((self.prefix_until - now) * 1000)))
                window.timeout(wait)
                try:
                    value = window.get_wch()
                except curses.error:
                    if deadline is not None and time.monotonic() >= deadline:
                        if timed:
                            return None
                        raise
                    continue
                result = self._feed(value, window, time.monotonic())
                if result is not None:
                    return result
                consumed += 1
                if consumed >= 64 or (delay > 0 and time.monotonic() >= deadline):
                    return None
        finally:
            window.timeout(delay)


def serial_monitor(redraw):
    """Use size queries on physical serial consoles, keeping SSH and VTs native."""
    if not sys.platform.startswith('linux') or not os.environ.get('TERM', '').startswith(
            ('xterm', 'screen', 'tmux', 'rxvt', 'vte', 'foot', 'kitty')):
        return None
    try:
        input_fd, output_fd = sys.stdin.fileno(), sys.stdout.fileno()
        if not os.isatty(input_fd) or not os.isatty(output_fd):
            return None
        if os.ttyname(input_fd).startswith('/dev/pts/'):
            return None
        try:
            fcntl.ioctl(input_fd, 0x4B3B, b'\0' * 4)  # KDGETMODE: real Linux VT.
        except OSError:
            return SerialResize(input_fd, output_fd, redraw)
    except (AttributeError, OSError, ValueError):
        pass
    return None
