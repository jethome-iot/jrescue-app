"""
Input Handler for GPIO buttons via evdev
"""

import evdev
from evdev import InputDevice, categorize, ecodes
import time
import config


class InputHandler:
    """Handle input from GPIO buttons"""

    def __init__(self, exclusive=True):
        """
        Initialize input device

        Args:
            exclusive: If True, grab device exclusively (prevents events from
                      going to terminal/other apps). Default: True
        """
        self.device = self._find_gpio_keys_device()
        if not self.device:
            raise RuntimeError("GPIO keys device not found. Check if gpio-keys is loaded.")

        self._is_grabbed = False
        self._is_closed = False

        # Grab device exclusively to prevent events going to terminal
        if exclusive:
            try:
                self.device.grab()
                self._is_grabbed = True
                print(f"✓ GPIO device grabbed exclusively (events won't go to terminal)")
            except Exception as e:
                print(f"⚠ Warning: Could not grab device exclusively: {e}")

        # Last key press time for debouncing
        self.last_key_time = 0
        self.debounce_delay = config.BUTTON_DEBOUNCE_MS / 1000.0

    def _find_gpio_keys_device(self):
        """Find the input device for gpio-keys"""
        devices = [InputDevice(path) for path in evdev.list_devices()]

        # PRIORITY 1: Look for gpio-keys specifically (most reliable)
        for device in devices:
            name_lower = device.name.lower()
            if 'gpio-keys' in name_lower or name_lower == 'gpio-keys':
                print(f"Found GPIO device: {device.name} at {device.path}")
                return device

        # PRIORITY 2: Look for devices with "gpio" in name
        for device in devices:
            name_lower = device.name.lower()
            if 'gpio' in name_lower:
                print(f"Found GPIO device: {device.name} at {device.path}")
                return device

        # PRIORITY 3: Look for devices with "button" in name
        for device in devices:
            name_lower = device.name.lower()
            if 'button' in name_lower:
                print(f"Found button device: {device.name} at {device.path}")
                return device

        # PRIORITY 4: Try to find by capabilities (KEY_UP, KEY_DOWN, KEY_ENTER, KEY_HOME)
        for device in devices:
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                # Check if it has our specific GPIO keys (not just any keyboard)
                if (ecodes.KEY_UP in keys and
                    ecodes.KEY_DOWN in keys and
                    ecodes.KEY_ENTER in keys and
                    ecodes.KEY_HOME in keys and
                    ecodes.KEY_LEFT in keys and
                    ecodes.KEY_RIGHT in keys):
                    # Exclude full keyboards by checking if it DOESN'T have letter keys
                    has_letters = any(k in keys for k in range(ecodes.KEY_A, ecodes.KEY_Z + 1))
                    if not has_letters:
                        print(f"Found compatible device: {device.name} at {device.path}")
                        return device

        return None

    def _is_debounced(self):
        """Check if enough time has passed since last key press"""
        current_time = time.time()
        if current_time - self.last_key_time < self.debounce_delay:
            return False
        self.last_key_time = current_time
        return True

    def wait_for_key(self):
        """
        Wait for key press and return key code (blocking)

        Returns:
            Key code (from ecodes)
        """
        for event in self.device.read_loop():
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)
                # Only process key down events
                if key_event.keystate == 1:  # Key down
                    if self._is_debounced():
                        return event.code

    def get_key_nonblocking(self, timeout=0.1):
        """
        Get key if pressed, return None if no key (non-blocking)

        Args:
            timeout: Timeout in seconds

        Returns:
            Key code or None
        """
        try:
            # Set device to non-blocking mode
            import select

            # Wait for input with timeout
            r, w, x = select.select([self.device.fd], [], [], timeout)

            if r:
                for event in self.device.read():
                    if event.type == ecodes.EV_KEY:
                        key_event = categorize(event)
                        if key_event.keystate == 1:  # Key down
                            if self._is_debounced():
                                return event.code
        except Exception:
            pass

        return None

    def flush_events(self):
        """Flush all pending events"""
        try:
            while True:
                event = self.get_key_nonblocking(timeout=0)
                if event is None:
                    break
        except Exception:
            pass

    def release(self):
        """Release device (ungrab) so other apps can use it"""
        if self._is_grabbed and not self._is_closed:
            try:
                self.device.ungrab()
                self._is_grabbed = False
                print("✓ GPIO device released")
            except Exception as e:
                print(f"⚠ Warning: Could not release device: {e}")

    def cleanup(self):
        """Cleanup and close device"""
        if not self._is_closed:
            self.release()
            try:
                self.device.close()
                self._is_closed = True
            except Exception:
                pass

    def __del__(self):
        """Destructor - automatically cleanup on object deletion"""
        try:
            self.cleanup()
        except Exception:
            pass


# Key code constants for convenience
KEY_UP = ecodes.KEY_UP
KEY_DOWN = ecodes.KEY_DOWN
KEY_LEFT = ecodes.KEY_LEFT
KEY_RIGHT = ecodes.KEY_RIGHT
KEY_ENTER = ecodes.KEY_ENTER
KEY_BACK = ecodes.KEY_BACK
KEY_HOME = ecodes.KEY_HOME


class TestInputHandler:
    """Test input handler for running without physical buttons"""

    def __init__(self):
        """Initialize test handler"""
        print("⚠️  TEST MODE: No physical buttons, using simulated input")
        self.last_key_time = 0
        self.debounce_delay = 0.1

    def wait_for_key(self):
        """Simulate key press after delay"""
        time.sleep(2)
        return KEY_ENTER

    def get_key_nonblocking(self, timeout=0.1):
        """Always return None (no input in test mode)"""
        time.sleep(timeout)
        return None

    def flush_events(self):
        """No-op for test mode"""
        pass

