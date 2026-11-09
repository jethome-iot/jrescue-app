"""Handle OLED inactivity on the UI thread and consume the wake-up gesture."""

import time

DEFAULT_TIMEOUT = 60
TIMEOUT_OPTIONS = (30, 60, 0)


class IdleScreen:
    """Sleep only while waiting in menus; busy operations stay visible."""

    def __init__(self, display, buttons, timeout=DEFAULT_TIMEOUT, clock=None):
        self.display = display
        self.buttons = buttons
        self.clock = clock or time.monotonic
        self.timeout = timeout
        self.sleeping = False
        self._waking = False
        self.last_activity = self.clock()

    def activity(self):
        """Wake if needed and begin a fresh inactivity interval."""
        if self.sleeping:
            self.display.wake()
            self.sleeping = False
        self.last_activity = self.clock()

    def set_timeout(self, seconds):
        """Keep the selection in RAM; zero disables automatic screen sleep."""
        if seconds not in TIMEOUT_OPTIONS:
            raise ValueError('Unsupported screen timeout')
        self.activity()
        self.timeout = seconds

    def wait_for_key(self, timeout=None):
        """Preserve caller deadlines, swallowing wake keys until all are released."""
        deadline = None if timeout is None else self.clock()+max(0, timeout)
        while True:
            now = self.clock()
            remaining = None if deadline is None else max(0, deadline-now)
            if remaining == 0:
                return None
            if self._waking:
                # A held wake button, its repeats and any simultaneous buttons
                # must not navigate, submit a password or arm a power action.
                if not self.buttons.get_pressed_keys():
                    self.buttons.flush_events()
                    self._waking = False
                    self.activity()
                else:
                    delay = 0.1 if remaining is None else min(0.1, remaining)
                    self.buttons.read_key_events(timeout=delay)
                    self.last_activity = self.clock()
                continue
            if not self.sleeping and self.timeout:
                until_sleep = self.timeout-(now-self.last_activity)
                if until_sleep <= 0:
                    self.display.sleep()
                    self.sleeping = True
                else:
                    remaining = until_sleep if remaining is None else min(remaining, until_sleep)
            key = self.buttons.wait_for_key(timeout=remaining)
            if key is None:
                continue
            if self.sleeping:
                self.activity()
                self._waking = True
                continue
            self.activity()
            return key
