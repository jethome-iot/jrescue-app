"""
OLED Display Manager using Linux Framebuffer
Works with kernel driver (ssd130x-i2c) managing the display via /dev/fb1
"""

import os
import mmap
import subprocess
from PIL import Image, ImageDraw, ImageFont
import config


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

            # Framebuffer parameters (from kernel driver)
            self.stride = 512  # bytes per line (128 pixels * 4 bytes/pixel)
            self.bpp = 4       # bytes per pixel (32-bit BGRA)
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

            # Load fonts
            self.font_small = self._load_font(config.FONT_SMALL)
            self.font_normal = self._load_font(config.FONT_NORMAL)

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

    def set_brightness_max(self):
        """
        Set display brightness to maximum to minimize PWM flicker.
        This helps reduce flickering when viewed through phone cameras.
        """
        brightness_paths = [
            '/sys/devices/platform/soc/ffd00000.bus/ffd1c000.i2c/i2c-0/0-003c/backlight/0-003c/brightness',
            '/sys/class/backlight/*/brightness',
        ]

        import glob

        for pattern in brightness_paths:
            paths = glob.glob(pattern)
            for path in paths:
                try:
                    # Read max brightness first
                    max_path = path.replace('/brightness', '/max_brightness')
                    if os.path.exists(max_path):
                        with open(max_path, 'r') as f:
                            max_brightness = int(f.read().strip())
                    else:
                        max_brightness = 255  # Default max

                    # Set to maximum
                    with open(path, 'w') as f:
                        f.write(str(max_brightness))
                    print(f"✓ Set brightness to {max_brightness} via {path}")
                    return True
                except (IOError, PermissionError, ValueError) as e:
                    continue

        print("⚠ Could not set brightness (not critical)")
        return False

    def _load_font(self, size):
        """Load font, trying multiple paths"""
        for font_path in config.FONT_PATHS:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    continue
        # Fallback to default font
            return ImageFont.load_default()

    def _truncate(self, text, max_length):
        """Truncate text to max length (legacy, use _wrap_text instead)"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(config.TEXT_TRUNCATE)] + config.TEXT_TRUNCATE

    def _wrap_text(self, text, max_width, first_line_indent=False):
        """
        Wrap text to fit within max_width characters per line.
        Returns list of lines.

        Args:
            text: Text to wrap
            max_width: Maximum characters per line
            first_line_indent: If True, first line uses max_width, others use full width (18)
        """
        if not text:
            return ['']

        text = str(text)

        # If text contains newlines, split by them first
        if '\n' in text:
            existing_lines = text.split('\n')
            all_lines = []
            for idx, line in enumerate(existing_lines):
                # First line uses max_width (for numbering), subsequent lines use full width
                if first_line_indent and idx == 0:
                    line_width = max_width
                else:
                    # Subsequent lines can use full width (18 chars at 128px width)
                    line_width = 18 if first_line_indent else max_width
                wrapped = self._wrap_single_line(line, line_width)
                all_lines.extend(wrapped)
            return all_lines if all_lines else ['']
        else:
            # No newlines - just wrap normally
            return self._wrap_single_line(text, max_width)

    def _wrap_single_line(self, text, max_width):
        """Wrap a single line of text"""
        if not text:
            return ['']

        words = text.split(' ')
        lines = []
        current_line = ''

        for word in words:
            # If word alone is longer than max_width, split it
            if len(word) > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = ''
                # Split long word into chunks
                for i in range(0, len(word), max_width):
                    lines.append(word[i:i+max_width])
                continue

            # Try adding word to current line
            test_line = current_line + (' ' if current_line else '') + word

            if len(test_line) <= max_width:
                current_line = test_line
            else:
                # Current line is full, start new line
                if current_line:
                    lines.append(current_line)
                current_line = word

        # Add last line
        if current_line:
            lines.append(current_line)

        return lines if lines else ['']

    def _update_display(self):
        """Write PIL image to framebuffer (convert 1-bit to 32-bit BGRA)"""
        try:
            # Create raw framebuffer data (32-bit BGRA format)
            raw_data = bytearray(self.fb_size)

            # Convert 1-bit PIL image to 32-bit BGRA
            for y in range(self.height):
                for x in range(self.width):
                    offset = y * self.stride + x * self.bpp
                    pixel = self.image.getpixel((x, y))

                    if pixel > 0:  # White pixel
                        raw_data[offset + 0] = 255  # B
                        raw_data[offset + 1] = 255  # G
                        raw_data[offset + 2] = 255  # R
                        raw_data[offset + 3] = 0    # A
                    else:  # Black pixel
                        raw_data[offset + 0] = 0    # B
                        raw_data[offset + 1] = 0    # G
                        raw_data[offset + 2] = 0    # R
                        raw_data[offset + 3] = 0    # A

            # Write to framebuffer
            self.fb_mmap.seek(0)
            self.fb_mmap.write(raw_data)
            self.fb_mmap.flush()

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

    def draw_text_screen(self, lines, selected_index=-1):
        """Draw text screen with optional selection highlight"""
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        y = 0
        line_height = 14  # For font size 12

        for i, line in enumerate(lines[:4]):  # Max 4 lines (font is bigger)
            # Truncate if needed
            text = self._truncate(str(line), config.MAX_LINE_LENGTH)

            # Highlight selected line
            if i == selected_index:
                # Draw filled rectangle for highlight
                self.draw.rectangle((0, y, self.width, y + line_height), fill=1)
                # Draw inverted text
                self.draw.text((0, y), text, font=self.font_small, fill=0)
            else:
                # Normal text
                self.draw.text((0, y), text, font=self.font_small, fill=1)

            y += line_height

        self._update_display()

    def draw_menu(self, title, items, selected_index):
        """Draw menu with title and items"""
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        y = 0

        # Draw title separator if title provided (same font size as items)
        if title:
            self.draw.text((0, y), self._truncate(title, config.MAX_LINE_LENGTH),
                          font=self.font_small, fill=1)
            y += 14
            self.draw.line((0, y, self.width, y), fill=1)
            y += 2
            row_spacing = 15  # With title, normal spacing
        else:
            # No title, no separator - menu starts at very top
            y = 0
            row_spacing = 14  # Without title, tighter spacing to fit 4 items

        # Draw menu items
        for i, item in enumerate(items[:4]):  # Max 4 items for font size 12
            # Check if we're still within screen bounds (text at y+1, font 12px + descenders ~4px = 20px safe margin)
            if y + 20 > self.height:
                break

            text = self._truncate(str(item), config.MAX_LINE_LENGTH)

            if i == selected_index:
                # Highlight selected item
                self.draw.rectangle((0, y, self.width, y + 14), fill=1)
                self.draw.text((2, y + 1), text, font=self.font_small, fill=0)
            else:
                self.draw.text((2, y + 1), text, font=self.font_small, fill=1)

            y += row_spacing

        self._update_display()

    def draw_grid_menu(self, items, selected_row, selected_col):
        """Draw 2x2 grid menu with centered text and border highlight"""
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        # Grid dimensions
        cell_width = self.width // 2  # 64px
        cell_height = self.height // 2  # 32px

        # Draw 2x2 grid
        for row in range(2):
            for col in range(2):
                idx = row * 2 + col
                if idx >= len(items):
                    continue

                # Calculate cell position
                x = col * cell_width
                y = row * cell_height

                # Get item text
                item_text = str(items[idx])

                # Check if selected
                is_selected = (row == selected_row and col == selected_col)

                # Calculate safe bottom boundary (must not reach 64px!)
                # For bottom row: 32 + 32 = 64, so limit to 62
                max_y = min(y + cell_height - 1, self.height - 2)
                max_x = x + cell_width - 1

                # Draw border
                if is_selected:
                    # Draw very thick border (multiple rectangles for 4px effect)
                    # All rectangles must stay within screen bounds
                    self.draw.rectangle((x, y, max_x, max_y),
                                       outline=1, fill=0)
                    self.draw.rectangle((x + 1, y + 1, max_x - 1, max(y + 1, max_y - 1)),
                                       outline=1, fill=0)
                    self.draw.rectangle((x + 2, y + 2, max_x - 2, max(y + 2, max_y - 2)),
                                       outline=1, fill=0)
                    # Optional: invert inner area for even more emphasis
                    # self.draw.rectangle((x + 3, y + 3, max_x - 3, max(y + 3, max_y - 3)),
                    #                    outline=0, fill=1)
                else:
                    # Draw thin border (1px)
                    self.draw.rectangle((x, y, max_x, max_y),
                                       outline=1, fill=0)

                # Draw centered text (split lines if needed)
                lines = item_text.split('\n') if '\n' in item_text else [item_text]

                # Calculate text position (centered) - use 9px spacing for tighter fit
                line_spacing = 9
                # For top row (y=0): start from very top. For bottom row: shift up more
                if row == 0:
                    # Top row - minimal top margin (2px)
                    text_y_start = y + 2
                else:
                    # Bottom row - shift up to avoid overflow
                    text_y_start = y + (cell_height - len(lines) * line_spacing) // 2 - 4

                for i, line in enumerate(lines[:2]):  # Max 2 lines per cell
                    # Calculate text y position
                    text_y = text_y_start + i * line_spacing

                    # VERY STRICT check: text must fit COMPLETELY within cell AND screen bounds
                    # text_y + font(12) + descenders(4) + safety(2) = text_y + 18
                    # Also check against cell bottom boundary
                    if text_y + 18 > min(y + cell_height, self.height):
                        break  # Don't draw text that goes beyond cell or screen

                    # Truncate if too long (max ~8 chars for 64px width)
                    truncated = self._truncate(line, 8)

                    # Estimate text width (rough approximation: 7px per char for font 12)
                    text_width = len(truncated) * 7
                    text_x = x + (cell_width - text_width) // 2

                    self.draw.text((text_x, text_y), truncated,
                                  font=self.font_small, fill=1)

        self._update_display()

    def draw_message(self, title, message, wait_for_key=False):
        """Draw message screen with OK button at bottom"""
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        y = 0

        # Draw title if provided
        if title:
            self.draw.text((0, y), self._truncate(title, config.MAX_LINE_LENGTH),
                          font=self.font_small, fill=1)
            y += 14
            self.draw.line((0, y, self.width, y), fill=1)
            y += 2

        # Reserve space for OK button at bottom (20px for button position)
        max_message_height = self.height - 20

        # Message lines with automatic text wrapping
        # Pass entire message to _wrap_text to preserve newline logic
        # Use 18 chars width (no numbering in messages, can use full width)
        all_wrapped_lines = self._wrap_text(str(message), 18, first_line_indent=False)

        # Display lines, leaving space for OK button
        for text_line in all_wrapped_lines:
            # Check if current line will fit (use 14 for line height like in lists)
            if y + 14 > max_message_height:
                break
            self.draw.text((0, y), text_line, font=self.font_small, fill=1)
            y += 14

        # Draw OK button at bottom center (same style as horizontal_choice)
        button_y = self.height - 20
        button_text = "OK"
        button_height = 16

        # Calculate button size
        bbox = self.draw.textbbox((0, 0), button_text, font=self.font_small)
        text_width = bbox[2] - bbox[0]
        button_width = text_width + 16  # Add padding

        # Center button horizontally
        button_x = (self.width - button_width) // 2

        # Draw filled rectangle (selected style)
        self.draw.rectangle((button_x, button_y, button_x + button_width, button_y + button_height),
                          fill=1, outline=1)

        # Draw text centered in button (inverted colors)
        text_x = button_x + (button_width - text_width) // 2
        text_y = button_y + (button_height - 10) // 2
        self.draw.text((text_x, text_y), button_text, font=self.font_small, fill=0)

        self._update_display()

    def draw_progress(self, title, message, percent=None):
        """Draw progress screen with centered progress bar and percentage on top"""
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        y = 0

        # Draw title if provided
        if title:
            self.draw.text((0, y), self._truncate(title, config.MAX_LINE_LENGTH),
                          font=self.font_small, fill=1)
            y += 14
            self.draw.line((0, y, self.width, y), fill=1)
            y += 2

        # Progress bar and percentage in center
        if percent is not None:
            # Calculate center position
            # Screen height = 64px, after title = ~48px available
            # Put percentage and bar in vertical center

            # Percentage text (on top)
            pct_text = f"{int(percent)}%"
            bbox = self.draw.textbbox((0, 0), pct_text, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            pct_x = (self.width - text_width) // 2
            pct_y = 24  # Vertical position for percentage

            self.draw.text((pct_x, pct_y), pct_text, font=self.font_small, fill=1)

            # Progress bar (below percentage, centered)
            bar_height = 12
            bar_y = pct_y + 16  # 16px below percentage
            bar_width = int((self.width - 4) * (percent / 100))

            # Bar outline
            self.draw.rectangle((0, bar_y, self.width - 1, bar_y + bar_height),
                              outline=1, fill=0)

            # Filled bar (only draw if width is enough to avoid coordinate errors)
            if bar_width > 2:  # Must be > 2 because bar starts at x=2
                self.draw.rectangle((2, bar_y + 2, bar_width, bar_y + bar_height - 2),
                                  fill=1)

        self._update_display()

    def draw_spinner(self, title, message, frame=0):
        """Draw spinner animation"""
        spinner_chars = ['|', '/', '-', '\\']
        spinner = spinner_chars[frame % 4]

        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        y = 0

        # Draw title with spinner if provided
        if title:
            title_text = f"{self._truncate(title, config.MAX_LINE_LENGTH - 2)} {spinner}"
            self.draw.text((0, y), title_text, font=self.font_small, fill=1)
            y += 14
            self.draw.line((0, y, self.width, y), fill=1)
            y += 2

        # Message with automatic text wrapping
        max_lines = 3 if title else 4  # More space without title

        # Pass entire message to _wrap_text to preserve newline logic
        all_wrapped_lines = self._wrap_text(str(message), config.MAX_LINE_LENGTH, first_line_indent=False)

        # Display up to max_lines
        for text_line in all_wrapped_lines[:max_lines]:
            if y + 15 > self.height:
                break
            self.draw.text((0, y), text_line, font=self.font_small, fill=1)
            y += 15

        self._update_display()

    def draw_splash(self, title, version):
        """Draw splash screen (same font size for all)"""
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        # Centered title (same font as items)
        title_text = self._truncate(title, config.MAX_LINE_LENGTH)
        title_width = len(title_text) * 6  # Approximate
        x = (self.width - title_width) // 2
        self.draw.text((x, 20), title_text, font=self.font_small, fill=1)

        # Version
        version_text = self._truncate(version, config.MAX_LINE_LENGTH)
        version_width = len(version_text) * 5
        x = (self.width - version_width) // 2
        self.draw.text((x, 35), version_text, font=self.font_small, fill=1)

        self._update_display()

    def draw_horizontal_choice(self, title, option1, option2, selected):
        """
        Draw horizontal choice dialog (for OK/NO selection)

        Args:
            title: Dialog title (can be multi-line with \n)
            option1: First option text (left)
            option2: Second option text (right)
            selected: Selected option index (0 or 1)
        """
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        y = 2

        # Draw title (support multi-line)
        title_lines = title.split('\n')
        for line in title_lines[:2]:  # Max 2 lines for title
            text = self._truncate(line, config.MAX_LINE_LENGTH)
            self.draw.text((2, y), text, font=self.font_small, fill=1)
            y += 14

        y += 6  # Extra spacing before buttons

        # Draw horizontal buttons at bottom
        button_y = self.height - 20
        button_width = (self.width - 6) // 2  # Two buttons with 2px gap
        button_height = 16

        # Left button (option1)
        x1_left = 2
        x2_left = x1_left + button_width
        if selected == 0:
            # Filled background for selected
            self.draw.rectangle((x1_left, button_y, x2_left, button_y + button_height),
                              fill=1, outline=1)
            # Calculate text centering
            bbox = self.draw.textbbox((0, 0), option1, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_x = x1_left + (button_width - text_width) // 2
            text_y = button_y + (button_height - 10) // 2
            self.draw.text((text_x, text_y), option1, font=self.font_small, fill=0)
        else:
            # Just outline for unselected
            self.draw.rectangle((x1_left, button_y, x2_left, button_y + button_height),
                              fill=0, outline=1)
            bbox = self.draw.textbbox((0, 0), option1, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_x = x1_left + (button_width - text_width) // 2
            text_y = button_y + (button_height - 10) // 2
            self.draw.text((text_x, text_y), option1, font=self.font_small, fill=1)

        # Right button (option2)
        x1_right = x2_left + 2
        x2_right = self.width - 2
        if selected == 1:
            # Filled background for selected
            self.draw.rectangle((x1_right, button_y, x2_right, button_y + button_height),
                              fill=1, outline=1)
            bbox = self.draw.textbbox((0, 0), option2, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_x = x1_right + (button_width - text_width) // 2
            text_y = button_y + (button_height - 10) // 2
            self.draw.text((text_x, text_y), option2, font=self.font_small, fill=0)
        else:
            # Just outline for unselected
            self.draw.rectangle((x1_right, button_y, x2_right, button_y + button_height),
                              fill=0, outline=1)
            bbox = self.draw.textbbox((0, 0), option2, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_x = x1_right + (button_width - text_width) // 2
            text_y = button_y + (button_height - 10) // 2
            self.draw.text((text_x, text_y), option2, font=self.font_small, fill=1)

        self._update_display()

    def draw_keyboard(self, password, grid, cursor_row, cursor_col, hint=""):
        """
        Draw on-screen keyboard with 4x8 grid layout

        Args:
            password: Current password string
            grid: 4x8 array of characters/buttons
            cursor_row: Selected row (0-3)
            cursor_col: Selected column (0-7)
            hint: Optional hint text (e.g., SSID)
        """
        # Clear entire screen first (PIL Image)
        from PIL import Image, ImageDraw
        self.image = Image.new('1', (self.width, self.height), color=0)
        self.draw = ImageDraw.Draw(self.image)

        # Top bar - show "Pass: " + password
        y = 0
        # "Pass: " takes ~30px, leaving ~98px for password (about 16 chars at font 12)
        max_pwd_len = 12  # Max characters to show
        password_display = password if len(password) <= max_pwd_len else password[-max_pwd_len:]
        pwd_text = f"Pass: {password_display}_"
        self.draw.text((0, y), pwd_text, font=self.font_small, fill=1)
        y += 13

        # Separator line
        self.draw.line((0, y, self.width - 1, y), fill=1)
        y += 2

        # Keyboard grid (49px remaining: 64 - 13 - 2 = 49)
        # 4 rows, each row 12px high (48px total, 1px gap at bottom)
        cell_width = self.width // 8  # 128 / 8 = 16px per cell
        cell_height = 12  # Height per row

        grid_start_y = y

        for row in range(4):
            for col in range(8):
                cell_x = col * cell_width
                cell_y = grid_start_y + row * cell_height

                # Get character/button text
                char = grid[row][col] if grid[row][col] else ""

                # Check if this cell is selected
                is_selected = (row == cursor_row and col == cursor_col)

                if is_selected:
                    # Draw selection with thick border
                    # Draw 2px border around cell
                    self.draw.rectangle((cell_x, cell_y, cell_x + cell_width - 1,
                                       cell_y + cell_height - 1), outline=1, width=2)

                # Draw character centered in cell
                if char:
                    # Get accurate text bounding box
                    bbox = self.draw.textbbox((0, 0), char, font=self.font_small)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]

                    # Center text in cell
                    text_x = cell_x + (cell_width - text_width) // 2
                    text_y = cell_y + (cell_height - text_height) // 2 - bbox[1]

                    # Draw text
                    self.draw.text((text_x, text_y), char, font=self.font_small, fill=1)

        self._update_display()

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
