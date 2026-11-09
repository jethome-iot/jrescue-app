"""
OLED Display Manager using the Linux framebuffer (/dev/fb0).

Adapts to whichever SSD130x kernel driver is present, reading geometry and
pixel format from the framebuffer via ioctl (never hardcoded):
  - legacy fbdev `ssd1307fb` (e.g. vendor 5.15): 1 bit/pixel, LSB = leftmost
    pixel, so we pack with PIL rawmode '1;R' (reversed bit order);
  - DRM `ssd130x` fbdev emulation (mainline): 32 bit/pixel XRGB.
"""

import os
import mmap
import fcntl
import struct
from PIL import Image, ImageDraw
import config
from render import OledRenderer

# Linux framebuffer ioctls (include/uapi/linux/fb.h)
FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602
FBIOBLANK = 0x4611
FB_BLANK_UNBLANK = 0
FB_BLANK_POWERDOWN = 4


class DisplayManager:
    """Manage OLED display output via framebuffer"""

    def __init__(self):
        """Initialize framebuffer display"""
        try:
            self.fb_device = config.FRAMEBUFFER_DEVICE

            # Check if framebuffer exists
            if not os.path.exists(self.fb_device):
                raise RuntimeError(f"Framebuffer device {self.fb_device} not found")

            # Activate framebuffer (disable blanking)
            self._activate_framebuffer()

            # Display parameters
            self.width = config.OLED_WIDTH
            self.height = config.OLED_HEIGHT

            # Open framebuffer device
            self.fb_fd = os.open(self.fb_device, os.O_RDWR | os.O_SYNC)

            # Framebuffer geometry/format is read from the kernel driver, not
            # hardcoded: the legacy ssd1307fb driver exposes a 1 bit/pixel
            # buffer (1024 bytes for 128x64), while a DRM ssd130x fbdev-emulated
            # panel exposes 32 bit/pixel. mmapping a hardcoded 32bpp size onto a
            # 1bpp buffer overruns it and the kernel kills us with SIGBUS.
            vinfo = fcntl.ioctl(self.fb_fd, FBIOGET_VSCREENINFO, bytes(160))
            v_xres, v_yres = struct.unpack_from('II', vinfo, 0)
            self.bpp_bits = struct.unpack_from('I', vinfo, 24)[0]  # bits_per_pixel
            if v_xres:
                self.width = v_xres
            if v_yres:
                self.height = v_yres

            finfo = fcntl.ioctl(self.fb_fd, FBIOGET_FSCREENINFO, bytes(80))
            # fb_fix_screeninfo.line_length: after id[16] + smem_start(ulong=8) +
            # smem_len(4)+type(4)+type_aux(4)+visual(4)+xpanstep/ypanstep/
            # ywrapstep(2*3)+reserved(2) -> offset 48 on 64-bit.
            self.stride = struct.unpack_from('I', finfo, 48)[0]
            if not self.stride:  # fall back if the driver reports 0
                self.stride = (self.width * max(self.bpp_bits, 1) + 7) // 8
            self.fb_size = self.stride * self.height

            # Memory map the framebuffer
            self.fb_mmap = mmap.mmap(
                self.fb_fd,
                self.fb_size,
                mmap.MAP_SHARED,
                mmap.PROT_WRITE | mmap.PROT_READ
            )

            # Create PIL image for drawing (1-bit monochrome)
            self.image = Image.new('1', (self.width, self.height))
            self.draw = ImageDraw.Draw(self.image)

            self.renderer = OledRenderer(self.width, self.height,
                                          config.FONT_PATHS, config.FONT_BOLD_PATHS,
                                          config.MAIN_FONT_PATHS, config.KEYBOARD_FONT_PATHS)
            self._last_frame = None
            self._sleeping = False
            self._hardware_blanked = False

            # Clear display on init
            self.clear()

        except Exception as e:
            raise RuntimeError(f"Failed to initialize OLED display: {e}")

    def _activate_framebuffer(self):
        """Activate framebuffer and disable blanking"""
        try:
            fb_num = self.fb_device.replace('/dev/fb', '')

            # Disable blanking
            try:
                with open(f'/sys/class/graphics/fb{fb_num}/blank', 'w') as f:
                    f.write('0')
            except Exception:
                pass  # Not critical if this fails

        except Exception as e:
            print(f"Warning: Could not activate framebuffer: {e}")

    def _update_display(self):
        """Write the PIL image to the framebuffer in its native pixel format."""
        if self._sleeping:
            return
        try:
            logical = self.image.tobytes()
            if logical == self._last_frame:
                return
            if self.bpp_bits == 1:
                row_bytes = (self.width + 7) // 8
                src = self.image.tobytes('raw', '1;R')
                if self.stride == row_bytes:
                    raw_data = src
                else:
                    # Driver reports a padded stride: pack row by row.
                    raw_data = bytearray(self.fb_size)
                    for y in range(self.height):
                        raw_data[y * self.stride:y * self.stride + row_bytes] = \
                            src[y * row_bytes:(y + 1) * row_bytes]
            else:
                bpp = max(self.bpp_bits // 8, 1)
                raw_data = bytearray(self.fb_size)
                px = self.image.load()
                for y in range(self.height):
                    row = y * self.stride
                    for x in range(self.width):
                        if px[x, y]:
                            off = row + x * bpp
                            raw_data[off + 0] = 255  # B
                            raw_data[off + 1] = 255  # G
                            raw_data[off + 2] = 255  # R

            # Write to framebuffer
            self.fb_mmap.seek(0)
            self.fb_mmap.write(raw_data)
            self.fb_mmap.flush()
            self._last_frame = logical

            # Force sync (optional, may improve reliability)
            try:
                os.fsync(self.fb_fd)
            except Exception:
                pass

        except Exception as e:
            print(f"Warning: Failed to update display: {e}")

    def clear(self):
        """Clear the display"""
        self.draw.rectangle((0, 0, self.width, self.height), fill=0)
        self._update_display()

    def sleep(self):
        """Ask the driver to blank; fall back to black pixels if unsupported."""
        if self._sleeping:
            return
        try:
            fcntl.ioctl(self.fb_fd, FBIOBLANK, FB_BLANK_POWERDOWN)
            self._hardware_blanked = True
        except OSError:
            self.fb_mmap.seek(0)
            self.fb_mmap.write(bytes(self.fb_size))
            self.fb_mmap.flush()
            self._hardware_blanked = False
        self._sleeping = True

    def wake(self):
        """Restore the latest logical frame; never navigate on the wake button."""
        if not self._sleeping:
            return
        if self._hardware_blanked:
            fcntl.ioctl(self.fb_fd, FBIOBLANK, FB_BLANK_UNBLANK)
        self._sleeping = False
        self._hardware_blanked = False
        self._last_frame = None
        self._update_display()

    def _present(self, image):
        """Write one complete frame, without intermediate transition frames."""
        self.image = image
        self.draw = ImageDraw.Draw(image)
        self.draw.fontmode = '1'
        self._update_display()

    def draw_text_screen(self, lines, selected_index=-1):
        """Render a compact text list with the shared fonts."""
        self._present(self.renderer.menu('', lines, selected_index, compact=True))

    def draw_menu(self, title, items, selected_index, compact=False, right=''):
        """Render outlined menu rows and a separate header counter/board label."""
        self._present(self.renderer.menu(title, items, selected_index, compact, right))

    def draw_main_menu(self, items, selected_index):
        """Show all four actions in one complete frame, with no transitions."""
        self._present(self.renderer.main_menu(items, selected_index))

    def draw_list(self, title, items, selected, current_num, total_num,
                  first_visible_num=1, can_scroll_up=False, can_scroll_down=False,
                  show_index=True, show_counter=True, icons=None, compact=False):
        """Render list pages whose geometry is also used by navigation."""
        image = self.renderer.list_screen(
            title, items, selected, current_num, total_num, first_visible_num,
            can_scroll_up, can_scroll_down, show_index, show_counter, icons, compact)
        self._present(image)

    def list_item_height(self, item, show_index=False, icon=None, compact=False):
        """Expose pixel-based pagination without duplicating drawing rules."""
        return self.renderer.list_item_height(item, show_index, icon, compact)

    def draw_message(self, title, message, wait_for_key=True):
        """Draw status text and its optional acknowledgement button."""
        self._present(self.renderer.message(title, message, button=wait_for_key))

    def draw_success(self, title, message, fraction=1, button=True):
        """Animate completion only after the operation actually succeeds."""
        self._present(self.renderer.success(title, message, fraction, button))

    def draw_progress(self, title, message, percent=None, detail=''):
        """Show actual operation progress; unknown progress uses the spinner."""
        if percent is None:
            self.draw_spinner(title, message, 0)
            return
        self._present(self.renderer.progress(title, message, percent, detail))

    def draw_spinner(self, title, message, frame=0):
        """Show a circular activity indicator."""
        self._present(self.renderer.spinner(title, message, frame))

    def draw_network_status(self, title, interface, link, ip, navigation='', counter=''):
        """Show a large address, status and current interface-page counter."""
        self._present(self.renderer.network_status(title, interface, link, ip,
                                                    navigation=navigation, counter=counter))

    def draw_info_page(self, title, value, detail=None, navigation='', counter=''):
        """Present a device/version snapshot without background polling."""
        self._present(self.renderer.info_page(title, value, detail, navigation=navigation, counter=counter))

    def draw_hold_confirmation(self, title, line1, line2, percent=0, plain_title=False):
        """Show a center-button hold, including its rollback after release."""
        self._present(self.renderer.hold_confirmation(title, line1, line2, percent,
                                                      plain_title=plain_title))

    def draw_splash(self, title, version):
        """Show the app version and detected board using the shared typography."""
        self._present(self.renderer.splash(title, version, config.JETHOME_DEVICE.upper()))

    def draw_horizontal_choice(self, title, option1, option2, selected):
        """Keep the existing safe default and confirmation controls."""
        self._present(self.renderer.horizontal_choice(title, option1, option2, selected))

    def draw_keyboard(self, password, grid, cursor_row, cursor_col, hint='', shift=0,
                      state=None, cursor_visible=True):
        """Show the full keyboard and its selected key without vertical scrolling."""
        self._present(self.renderer.keyboard(password, grid, cursor_row, cursor_col, hint, shift,
                                             state=state, cursor_visible=cursor_visible))

    def cleanup(self):
        """Clean up resources"""
        try:
            self.clear()
            if hasattr(self, 'fb_mmap'):
                self.fb_mmap.close()
            if hasattr(self, 'fb_fd'):
                os.close(self.fb_fd)
        except Exception:
            pass

    def __del__(self):
        """Destructor"""
        self.cleanup()
