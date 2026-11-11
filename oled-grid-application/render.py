"""Four-item OLED grid and HAOS-style screens, independent of hardware."""

from functools import lru_cache
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from keyboard_layout import (SHIFT, BACKSPACE, SPACE, SUBMIT, NUMBERS, LETTERS,
                             SYMBOLS, PASSWORD_HEIGHT, PASSWORD_FONT_SIZE, CONTROL_HEIGHT,
                             PASSWORD_BASELINE, PASSWORD_TEXT_X, KEY_BASELINE,
                             KeyboardState, key_rectangles)


class OledRenderer:
    """Readable grid captions, compact text spacing and circular feedback."""

    HEADER_HEIGHT = 16
    BODY_TOP = 19
    LINE_HEIGHT = 20
    TOP_ROW = (21, 37)
    BOTTOM_ROW = (41, 57)
    SSID_ROWS = ((21, 33), (34, 46))
    BUTTON_TOP = 42
    BUTTON_BOTTOM = 61
    BUTTON_BOXES = ((2, BUTTON_TOP, 61, BUTTON_BOTTOM),
                    (66, BUTTON_TOP, 125, BUTTON_BOTTOM))

    def __init__(self, width, height, regular_paths, bold_paths,
                 main_paths=None, keyboard_paths=None):
        self.width, self.height = width, height
        self.regular_paths, self.bold_paths = regular_paths, bold_paths
        self.main_paths = regular_paths if main_paths is None else main_paths
        self.keyboard_paths = regular_paths if keyboard_paths is None else keyboard_paths
        self._fonts = {}
        self.font_menu = self.font(14)
        self.font_caption = self.font(13)
        self.font_header = self.font(14)
        self.font_value = self.font(14)
        self.font_keyboard = self.font(15, family='keyboard')
        self.font_progress = self.font(19)
        _, self._measure_draw = self.canvas()

    @staticmethod
    def _load_font(paths, size):
        """Accept Buildroot's and conventional desktop DejaVu locations."""
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default()

    def font(self, size, bold=False, family='body'):
        """Cache each font size used to fit real translated strings."""
        key = size, bold, family
        if key not in self._fonts:
            paths = self.main_paths if family == 'main' else (
                self.keyboard_paths if family == 'keyboard' else
                self.bold_paths if bold else self.regular_paths)
            self._fonts[key] = self._load_font(paths, size)
        return self._fonts[key]

    def canvas(self):
        """Keep the physical OLED strictly monochrome."""
        image = Image.new('1', (self.width, self.height))
        draw = ImageDraw.Draw(image)
        draw.fontmode = '1'
        return image, draw

    @staticmethod
    @lru_cache(maxsize=128)
    def _stem_pixels(character, face):
        """Locate the extra column in f/F's doubled vertical stroke."""
        mask = face.getmask(character, mode='1')
        bounds = mask.getbbox()
        if bounds is None:
            return ()
        glyph = Image.new('1', mask.size)
        glyph.putdata(mask)
        glyph = glyph.crop(bounds)
        if glyph.width < 2:
            return ()
        counts = [sum(bool(glyph.getpixel((x, y))) for y in range(glyph.height))
                  for x in range(glyph.width)]
        stem = max(range(glyph.width-1), key=lambda x: min(counts[x:x+2]))
        if min(counts[stem:stem+2]) <= glyph.height//2:
            return ()
        return tuple((stem+1, y) for y in range(glyph.height)
                     if glyph.getpixel((stem, y)) and glyph.getpixel((stem+1, y))
                     and (stem == 0 or not glyph.getpixel((stem-1, y)))
                     and (stem+2 == glyph.width or not glyph.getpixel((stem+2, y))))

    @staticmethod
    @lru_cache(maxsize=512)
    def _glyphs(value, face):
        """Crop ink and correct the body font's heavier f/F stems."""
        x0, y0, x1, y1 = face.getbbox(value)
        mask = Image.new('1', (max(1, x1-x0)+8, max(1, y1-y0)+8))
        draw = ImageDraw.Draw(mask)
        draw.fontmode = '1'
        draw.text((4-x0, 4-y0), value, font=face, fill=1)
        if ('f' in value or 'F' in value) and Path(
                getattr(face, 'path', '')).name == 'LiberationSans-Regular.ttf':
            for index, character in enumerate(value):
                if character not in 'fF':
                    continue
                # Preserve shaping and spacing; remove only the duplicate stem.
                advance = draw.textlength(value[:index+1], font=face)-draw.textlength(character, font=face)
                gx, gy, _, _ = face.getbbox(character)
                ink = face.getmask(character, mode='1').getbbox()
                if ink is None:
                    continue
                left, top = round(4-x0+advance)+gx+ink[0], 4-y0+gy+ink[1]
                for x, y in OledRenderer._stem_pixels(character, face):
                    mask.putpixel((left+x, top+y), 0)
        bounds = mask.getbbox()
        return mask.crop(bounds) if bounds else Image.new('1', (1, 1))

    def text_width(self, value, font=None):
        """Measure pixel widths, including Cyrillic and punctuation."""
        value = str(value)
        if font is self.font(PASSWORD_FONT_SIZE, family='keyboard'):
            return sum(self.password_character(char)[2] for char in value)
        return self._measure_draw.textlength(value, font=font or self.font_menu)

    def clip(self, value, width, font=None):
        """Keep the ellipsis within the available pixel width."""
        value, font = str(value), font or self.font_menu
        if self.text_width(value, font) <= width:
            return value
        while value and self.text_width(value+'…', font) > width:
            value = value[:-1]
        return value+'…' if self.text_width('…', font) <= width else ''

    def label(self, draw, box, value, size=14, bold=False, minimum=12, fill=1,
              left=False, family='body'):
        """Fit readable glyphs and center their actual ink on both axes."""
        x0, y0, x1, y1 = box
        width, height = x1-x0+1, y1-y0+1
        value = str(value)
        for point_size in range(size, minimum-1, -1):
            face = self.font(point_size, bold, family)
            glyphs = self._glyphs(value, face)
            if glyphs.width <= width and glyphs.height <= height:
                break
        else:
            value = self.clip(value, width, face)
            glyphs = self._glyphs(value, face)
        x = x0 if left else x0+(width-glyphs.width)//2
        draw.bitmap((x, y0+(height-glyphs.height)//2), glyphs, fill=fill)

    def wrap(self, value, width, font=None):
        """Preserve newlines and split long filenames or SSIDs by pixel width."""
        font = font or self.font_menu
        lines = []
        for paragraph in str(value).split('\n'):
            current = ''
            for character in paragraph:
                if current and self.text_width(current+character, font) > width:
                    split = current.rfind(' ')
                    if split > 0:
                        lines.append(current[:split])
                        current = current[split+1:]+character
                    else:
                        lines.append(current)
                        current = character
                else:
                    current += character
            lines.append(current.rstrip())
        return lines or ['']

    def header(self, draw, title, right='', page=None, right_width=0):
        """Separate a plain white title from the body with a one-pixel rule."""
        draw.rectangle((0, 0, self.width-1, 16), fill=0)
        text_reserved = int(self.text_width(right, self.font(12)))+7 if right else 0
        reserved = 27 if page is not None else text_reserved
        reserved = max(reserved, right_width)
        self.label(draw, (1, 0, self.width-2-reserved, 12), title, 14,
                   minimum=12, left=True)
        if page is not None:
            for index in range(4):
                x = self.width-25+index*6
                draw.rectangle((x, 5, x+2, 7), outline=1, fill=1 if index == page else 0)
        elif right:
            self.label(draw, (self.width-text_reserved, 0, self.width-2, 12), right, 12, minimum=12)
        draw.line((0, 15, self.width-1, 15), fill=1)

    @staticmethod
    def _point(cx, cy, radius, angle):
        """Start circular progress at twelve o'clock."""
        angle = math.radians(angle-90)
        return round(cx+radius*math.cos(angle)), round(cy+radius*math.sin(angle))

    def ring(self, draw, cx, cy, radius, percent=None, width=3):
        """An arc denotes measured progress; the dotted track is neutral."""
        for angle in range(0, 360, 15):
            draw.point(self._point(cx, cy, radius-1, angle), fill=1)
        if percent is not None and percent > 0:
            draw.arc((cx-radius, cy-radius, cx+radius, cy+radius),
                     -90, -90+360*min(100, percent)/100, fill=1, width=width)

    def two_rows(self, draw, x0, x1, upper, lower, size=17, bold=False):
        """Share a compact line pitch across messages, progress and hold screens."""
        self.label(draw, (x0, self.TOP_ROW[0], x1, self.TOP_ROW[1]), upper, size, bold)
        self.label(draw, (x0, self.BOTTOM_ROW[0], x1, self.BOTTOM_ROW[1]), lower, 14)

    def icon(self, draw, name, x, y, size=14):
        """Draw small menu icons without external bitmap assets."""
        cx, cy = x+size//2, y+size//2
        if name in ('network', 'wifi'):
            cy = y+size-2
            for radius in (size//2, size//3, size//6):
                draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), 220, 320, fill=1)
            draw.rectangle((cx-1, cy-1, cx+1, cy+1), fill=1)
        elif name == 'ethernet':
            draw.rounded_rectangle((x+1, y+2, x+size-2, y+size-5), radius=2, outline=1)
            for offset in range(4):
                px = x+3+offset*2
                draw.line((px, y+4, px, y+6), fill=1)
            draw.line((cx, y+size-5, cx, y+size-1), fill=1)
            draw.line((x+3, y+size-1, x+size-4, y+size-1), fill=1)
        elif name in ('flash', 'download'):
            draw.line((cx, y, cx, y+size-7), fill=1, width=2)
            draw.line((cx-4, y+size-11, cx, y+size-7, cx+4, y+size-11), fill=1)
            draw.rounded_rectangle((x+1, y+size-5, x+size-2, y+size-1), radius=1, outline=1)
        elif name in ('language', 'info', 'settings'):
            draw.ellipse((x+1, y+1, x+size-2, y+size-2), outline=1)
            draw.line((cx, y+3, cx, y+size-4), fill=1)
            draw.line((x+3, cy, x+size-4, cy), fill=1)
        elif name == 'reboot':
            draw.arc((x+1, y+2, x+size-2, y+size-1), -45, 225, fill=1, width=2)
            draw.line((cx, y, cx, cy), fill=1, width=2)
        elif name == 'usb':
            draw.rounded_rectangle((x+3, y+4, x+size-4, y+size-1), radius=1, outline=1)
            draw.rectangle((x+4, y, x+size-5, y+4), outline=1)

    def main_icon(self, draw, name, cx, top):
        """Use broad, high-contrast shapes in the grid's short icon area."""
        if name == 'network':
            for radius in (10, 6, 2):
                draw.arc((cx-radius, top+13-radius, cx+radius, top+13+radius),
                         210, 330, fill=1, width=2)
            draw.rectangle((cx-1, top+13, cx+1, top+14), fill=1)
        elif name == 'flash':
            draw.line((cx, top+2, cx, top+9), fill=1, width=2)
            draw.line((cx-4, top+5, cx, top+9, cx+4, top+5), fill=1, width=2)
            draw.rounded_rectangle((cx-10, top+11, cx+10, top+14), radius=1, outline=1)
        elif name == 'info':
            draw.ellipse((cx-7, top+2, cx+7, top+14), outline=1, width=2)
            draw.rectangle((cx-1, top+5, cx, top+6), fill=1)
            draw.line((cx, top+8, cx, top+11), fill=1, width=2)
        else:
            cy = top+9
            points = [self._point(cx, cy, radius, tooth*45+offset)
                      for tooth in range(8)
                      for offset, radius in ((-19, 5), (-12, 7), (12, 7), (19, 5))]
            draw.polygon(points, fill=1)
            draw.ellipse((cx-2, cy-2, cx+2, cy+2), fill=0)

    def main_menu(self, items, selected):
        """Show four fixed captions and icons without an extra header or telemetry."""
        image, draw = self.canvas()
        cell_width, cell_height = self.width//2, self.height//2
        for index, (value, name) in enumerate(zip(items, ('network', 'flash', 'info', 'settings'))):
            x, y = index % 2*cell_width, index//2*cell_height
            if index == selected:
                draw.rounded_rectangle((x, y, x+cell_width-1, y+cell_height-1),
                                       radius=4, outline=1)
            self.main_icon(draw, name, x+cell_width//2, y)
            self.label(draw, (x+3, y+17, x+cell_width-4, y+cell_height-3),
                       value, 14, False, 13, family='main')
        return image

    @staticmethod
    def list_text_x(show_index=False, icon=None):
        """Reserve columns consistently for both measuring and drawing."""
        return 7+(22 if show_index else 0)+(20 if icon else 0)

    def list_lines(self, item, show_index=False, icon=None, compact=False):
        """Keep long filenames readable, with at most two lines per page."""
        width = self.width-self.list_text_x(show_index, icon)-5
        face = self.font(12) if compact else self.font_value
        lines = self.wrap(item, width, face)
        if len(lines) > 2:
            lines = [lines[0], self.clip(lines[1]+'…', width, face)]
        return lines

    def list_item_height(self, item, show_index=False, icon=None, compact=False):
        """Measure the same row frames used to select and draw each item."""
        if len(self.list_lines(item, show_index, icon, compact)) == 1:
            return self.LINE_HEIGHT
        rows = self.SSID_ROWS if compact else (self.TOP_ROW, self.BOTTOM_ROW)
        return rows[-1][1]-rows[0][0]+4

    def menu(self, title, items, selected, compact=False, right=''):
        """Scroll using the same per-item budget as the drawing code."""
        start = 0
        while start < max(0, selected) and sum(self.list_item_height(item)
                for item in items[start:selected+1]) > self.height-self.BODY_TOP:
            start += 1
        end, used = start, 0
        while end < len(items):
            height = self.list_item_height(items[end])
            if used+height > self.height-self.BODY_TOP:
                break
            used += height
            end += 1
        image = self.list_screen(title, items[start:end], selected-start, selected+1,
                                 len(items), start+1, start > 0, end < len(items),
                                 show_index=False, show_counter=True)
        if right:
            self.header(ImageDraw.Draw(image), title, right)
        return image

    def list_screen(self, title, items, selected, current_num, total_num,
                    first_visible_num=1, can_scroll_up=False, can_scroll_down=False,
                    show_index=True, show_counter=True, icons=None, compact=False):
        """Use the same compact two-row layout for actions and wrapped names."""
        image, draw = self.canvas()
        counter = '{}/{}'.format(current_num, total_num) if show_counter else ''
        self.page_header(draw, title, right=counter)
        used = 0
        for index, item in enumerate(items):
            name = icons[index] if icons else None
            lines = self.list_lines(item, show_index, name, compact)
            height = self.list_item_height(item, show_index, name, compact)
            if used+height > self.height-self.BODY_TOP:
                break
            used += height
            wrapped_slots = self.SSID_ROWS if compact else (self.TOP_ROW, self.BOTTOM_ROW)
            slots = wrapped_slots if len(lines) == 2 else (
                self.TOP_ROW if index == 0 else self.BOTTOM_ROW,)
            active = index == selected
            if active:
                draw.rounded_rectangle((1, slots[0][0]-2, self.width-2,
                                        min(self.height-1, slots[-1][1]+1)), radius=3, fill=1)
            ink = 0 if active else 1
            top, bottom = slots[0]
            if show_index:
                self.label(draw, (4, top, 27, bottom), str(first_visible_num+index)+'.',
                           12 if compact else 13, fill=ink, left=True)
            x = self.list_text_x(show_index, name)
            if name:
                stamp = Image.new('1', (14, 14))
                self.icon(ImageDraw.Draw(stamp), name, 0, 0)
                draw.bitmap((x-20, top+1), stamp, fill=ink)
            for line, (top, bottom) in zip(lines, slots):
                self.label(draw, (x, top, self.width-5, bottom), line,
                           12 if compact else 14, fill=ink, left=show_index or bool(name))
        return image

    def button(self, draw, box, value, active=True):
        """Center painted glyphs inside the frame, including Cyrillic."""
        draw.rounded_rectangle(box, radius=3, outline=1, width=2 if active else 1)
        self.label(draw, box, value, 13)

    def message(self, title, message, button=True):
        """Keep an acknowledgement frame separate from the message."""
        image, draw = self.canvas()
        lines = self.wrap(message, self.width-8)
        self.header(draw, title)
        if len(lines) <= 1 and button:
            self.label(draw, (3, 21, self.width-4, 37), lines[0], 16)
            self.button(draw, (43, self.BUTTON_TOP, 84, self.BUTTON_BOTTOM), 'OK')
        else:
            if len(lines) > 2:
                lines[1] = self.clip(lines[1]+'…', self.width-8)
            self.two_rows(draw, 4, self.width-5, lines[0],
                          lines[1] if len(lines) > 1 else '', 14, False)
        return image

    def page_header(self, draw, title, navigation='', right=''):
        """Use only the numeric position; accept legacy navigation hints silently."""
        self.header(draw, title, right)

    def info_page(self, title, value, detail=None, navigation='', counter=''):
        """Keep numeric labels on separate rows and wrap long product names."""
        image, draw = self.canvas()
        self.page_header(draw, title, navigation, counter)
        if detail is None:
            lines = self.wrap(value, self.width-8)
            value, detail = lines[0], lines[1] if len(lines) > 1 else ''
            if len(lines) > 2:
                detail = self.clip(detail+'…', self.width-8)
        self.two_rows(draw, 4, self.width-5, value, detail, 14, False)
        return image

    def network_status(self, title, interface, link, ip, navigation='', counter=''):
        """Show the address prominently, with no MAC address or link speed."""
        image, draw = self.canvas()
        self.page_header(draw, title, navigation, counter or interface)
        self.label(draw, (2, 20, self.width-3, 37), ip, 18, minimum=13)
        for x in range(10, self.width-10, 2):
            draw.point((x, 39), fill=1)
        self.label(draw, (4, self.BOTTOM_ROW[0], self.width-5, self.BOTTOM_ROW[1]), link, 15)
        return image

    def _network_field(self, row, ssid):
        """Measure exactly the value window used for drawing and scrolling."""
        is_ssid = row == 'SSID'
        if not is_ssid and not row.startswith('IP: '):
            return None
        face = self.font(14)
        prefix = self._glyphs('SSID:' if is_ssid else 'IP:', face)
        glyph = self._glyphs((ssid or '--') if is_ssid else row[4:], face)
        value_x = 2+prefix.width+4
        width = self.width-2-value_x
        marked = not is_ssid and glyph.width > width
        if marked:
            value_x += 6
            width -= 12
        return prefix, glyph, value_x, width, marked

    def network_scroll_limits(self, rows, ssid=None):
        """Return per-row pixel limits; short values and status labels stay still."""
        limits = []
        for row in rows:
            field = self._network_field(row, ssid)
            limits.append(max(0, field[1].width-field[3]) if field else 0)
        return limits

    def network_fields(self, title, rows, counter='', ssid=None, offsets=None):
        """Draw the approved labeled Ethernet/WiFi layout with fixed captions."""
        image, draw = self.canvas()
        self.page_header(draw, title, right=counter)
        boxes = ((2, 18, self.width-3, 31), (2, 33, self.width-3, 46),
                 (2, 48, self.width-3, 61)) if len(rows) == 3 else (
                     (2, 21, self.width-3, 37), (2, 41, self.width-3, 57))
        offsets = offsets or [0]*len(rows)
        for index, (row, box) in enumerate(zip(rows, boxes)):
            field = self._network_field(row, ssid)
            if field is None:
                self.label(draw, box, row, 14, minimum=13, left=True)
                continue
            prefix, glyph, value_x, width, marked = field
            x0, y0, x1, y1 = box
            draw.bitmap((x0, y0+(y1-y0+1-prefix.height)//2), prefix, fill=1)
            maximum = max(0, glyph.width-width)
            offset = min(max(0, offsets[index]), maximum)
            viewport = glyph.crop((offset, 0, min(glyph.width, offset+width), glyph.height))
            draw.bitmap((value_x, y0+(y1-y0+1-glyph.height)//2), viewport, fill=1)
            if marked:
                cy = (y0+y1)//2
                if offset:
                    draw.line((value_x-3, cy-3, value_x-6, cy, value_x-3, cy+3), fill=1)
                if offset < maximum:
                    draw.line((x1-3, cy-3, x1, cy, x1-3, cy+3), fill=1)
        return image

    def progress(self, title, message, percent, detail=''):
        """A single large measured value and two compact detail lines."""
        image, draw = self.canvas()
        self.header(draw, title)
        percent = max(0, min(100, percent))
        self.ring(draw, 24, 39, 21, percent)
        self.label(draw, (9, 29, 39, 49), str(round(percent)), 19, minimum=15)
        width = self.width-55
        if str(detail).startswith('/dev/'):
            detail = ''
        lines = self.wrap(message, width, self.font_value)
        upper = message if detail else lines[0]
        lower = detail or (lines[1] if len(lines) > 1 else '')
        self.two_rows(draw, 51, self.width-2, upper, lower, 14)
        return image

    def spinner(self, title, message, frame=0):
        """Animate only the activity arc while all labels remain stationary."""
        image, draw = self.canvas()
        self.header(draw, title)
        self.ring(draw, 22, 39, 18)
        start = int(frame)*30-90
        draw.arc((4, 21, 40, 57), start, start+65, fill=1, width=3)
        lines = self.wrap(message, self.width-49, self.font_menu)
        self.two_rows(draw, 47, self.width-2, lines[0],
                      lines[1] if len(lines) > 1 else '', 14, False)
        return image

    def success(self, title, message, fraction=1, button=True):
        """Draw a short checkmark once, then keep the completed frame still."""
        image, draw = self.canvas()
        self.header(draw, title)
        self.ring(draw, 22, 38, 18, 100)
        points = ((15, 38), (20, 43), (30, 32))
        distance = (math.sqrt(50)+math.sqrt(221))*max(0, min(1, fraction))
        if distance > 0:
            amount = min(1, distance/math.sqrt(50))
            draw.line((points[0], (round(15+5*amount), round(38+5*amount))), fill=1, width=2)
        if distance > math.sqrt(50):
            amount = min(1, (distance-math.sqrt(50))/math.sqrt(221))
            draw.line((points[1], (round(20+10*amount), round(43-11*amount))), fill=1, width=2)
        self.label(draw, (48, 21, self.width-2, 37), message, 14)
        if button:
            self.button(draw, (61, self.BUTTON_TOP, 119, self.BUTTON_BOTTOM), 'OK')
        return image

    def hold_confirmation(self, title, line1, line2, percent=0, plain_title=False):
        """A three-second center hold, with rollback drawn in the same geometry."""
        image, draw = self.canvas()
        if plain_title:
            self.label(draw, (2, 1, self.width-3, 17), title, 14)
            self.ring(draw, 22, 42, 18, max(0, min(100, percent)), width=4)
            draw.ellipse((19, 39, 25, 45), fill=1)
            lines = str(line1).split('\n')+[str(line2)]
            if len(lines) == 3:
                for index, text in enumerate(lines):
                    top = 19+15*index
                    self.label(draw, (47, top, self.width-2, top+13), text, 14, minimum=14)
            else:
                self.label(draw, (47, 23, self.width-2, 39), line1, 14)
                self.label(draw, (47, 43, self.width-2, 59), line2, 14)
            return image
        if not title:
            self.ring(draw, 22, 32, 20, max(0, min(100, percent)), width=4)
            draw.ellipse((19, 29, 25, 35), fill=1)
            lines = str(line1).split('\n', 1)
            top = 3 if line2 else 13
            self.label(draw, (47, top, self.width-2, top+16), lines[0], 14)
            self.label(draw, (47, top+20, self.width-2, top+36),
                       lines[1] if len(lines) > 1 else '', 14)
            if line2:
                self.label(draw, (47, 45, self.width-2, 61), line2, 14)
            return image
        self.header(draw, title)
        self.ring(draw, 22, 39, 18, max(0, min(100, percent)), width=4)
        draw.ellipse((19, 36, 25, 42), fill=1)
        self.two_rows(draw, 46, self.width-2, line1, line2, 14, False)
        return image

    def splash(self, title, version, board=''):
        """Use the same typography while the application starts."""
        image, draw = self.canvas()
        self.header(draw, 'JetHub', board)
        self.two_rows(draw, 4, self.width-5, title, version, 17)
        return image

    def horizontal_choice(self, title, option1, option2, selected):
        """Retain NO as the initial choice without crowding its button frame."""
        image, draw = self.canvas()
        parts = str(title).split('\n')
        self.header(draw, parts[0])
        details = ' '.join(part.strip() for part in parts[1:] if part.strip())
        self.label(draw, (3, 21, self.width-4, 37), details, 15)
        for index, (box, value) in enumerate(zip(self.BUTTON_BOXES, (option1, option2))):
            self.button(draw, box, value, selected == index)
        return image

    @staticmethod
    @lru_cache(maxsize=1)
    def lower_l():
        """Distinguish lowercase l with a short hook at its top left."""
        image = Image.new('1', (3, 11))
        ImageDraw.Draw(image).line(((0, 1), (2, 0), (2, 10)), fill=1)
        return image

    @staticmethod
    def _punctuation_glyph(key, width, height):
        """Keep easily confused punctuation legible on the small panel."""
        image = Image.new('1', (width, height))
        draw = ImageDraw.Draw(image)
        cx, cy = (width-1)//2, (height-1)//2
        if key in '[]':
            sign = 1 if key == '[' else -1
            draw.line((cx+sign*2, cy-5, cx-sign*2, cy-5,
                       cx-sign*2, cy+5, cx+sign*2, cy+5), fill=1)
        elif key in '{}':
            sign = 1 if key == '{' else -1
            points = [(2, -5), (0, -5), (-1, -4), (-1, -2), (-3, 0),
                      (-1, 2), (-1, 4), (0, 5), (2, 5)]
            draw.line([(cx+sign*x, cy+y) for x, y in points], fill=1)
        elif key in '<>':
            sign = 1 if key == '<' else -1
            draw.line((cx+sign*3, cy-4, cx-sign*3, cy, cx+sign*3, cy+4), fill=1)
        elif key == '^':
            draw.line((cx-3, cy, cx, cy-4, cx+3, cy), fill=1)
        elif key == '|':
            draw.line((cx, cy-5, cx, cy+5), fill=1)
        elif key == '~':
            draw.line([(cx+x, cy+y) for x, y in
                       ((-4, 0), (-3, -1), (-2, -2), (-1, -2), (1, 0), (2, 0), (3, -1), (4, -2))], fill=1)
        elif key == '`':
            draw.line((cx-2, cy-4, cx, cy-2), fill=1)
        elif key == '.':
            draw.rectangle((cx, cy+4, cx+1, cy+5), fill=1)
        elif key == ',':
            draw.rectangle((cx, cy+3, cx+1, cy+4), fill=1)
            draw.line((cx+1, cy+4, cx, cy+6), fill=1)
        elif key == '_':
            draw.line((cx-4, cy+5, cx+4, cy+5), fill=1)
        elif key == '=':
            draw.line((cx-3, cy-1, cx+3, cy-1), fill=1)
            draw.line((cx-3, cy+2, cx+3, cy+2), fill=1)
        elif key in '\\/':
            sign = 1 if key == '\\' else -1
            draw.line((cx-sign*3, cy-5, cx+sign*3, cy+5), fill=1)
        return image, -(width//2), -KEY_BASELINE

    @lru_cache(maxsize=256)
    def keyboard_glyph(self, key, width, height):
        """Fit glyphs to their keys, preserving the three main rows' sizes."""
        if height == CONTROL_HEIGHT and key in ('.', '_'):
            image = Image.new('1', (width, height))
            draw = ImageDraw.Draw(image)
            cx = (width-1)//2
            if key == '.':
                draw.rectangle((cx, 5, cx+1, 6), fill=1)
            else:
                draw.line((cx-4, 6, cx+4, 6), fill=1)
            return image, -(width//2), -KEY_BASELINE
        if key == 'l':
            return self.lower_l(), -1, -KEY_BASELINE
        if key in '[]{}<>^|~`.,_=\\/':
            return self._punctuation_glyph(key, width, height)
        for size in range(15, 8, -1):
            face = self.font(size, family='keyboard')
            mask = Image.new('1', (32, 40))
            draw = ImageDraw.Draw(mask)
            draw.fontmode = '1'
            draw.text((16, 20), key, font=face, fill=1, anchor='ms')
            bounds = mask.getbbox()
            if bounds is None:
                return Image.new('1', (1, 1)), 0, 0
            if (bounds[1] >= 20-KEY_BASELINE and
                    bounds[3] <= 20+height-KEY_BASELINE and
                    bounds[0]-16 >= -(width//2) and bounds[2]-16 <= (width+1)//2):
                return mask.crop(bounds), bounds[0]-16, bounds[1]-20
        return mask.crop(bounds), bounds[0]-16, bounds[1]-20

    @lru_cache(maxsize=256)
    def password_character(self, character):
        """Reuse the character's actual key bitmap, including its fitted size."""
        face = self.font(PASSWORD_FONT_SIZE, family='keyboard')
        advance = self._measure_draw.textlength(character, font=face)
        if character == ' ':
            return Image.new('1', (1, 1)), 0, advance
        state = KeyboardState()
        for mode, shift in (('letters', 0), ('letters', 2), ('numbers', 0), ('symbols', 0)):
            state.mode, state.shift = mode, shift
            for row, keys in enumerate(self.keyboard_rectangles(state.rows)):
                for key, (x0, y0, x1, y1) in keys:
                    if key != character:
                        continue
                    mask, _, dy = self.keyboard_glyph(key, x1-x0+1, y1-y0+1)
                    bounds = mask.getbbox()
                    glyph = mask.crop(bounds)
                    # Footer symbols sit on the shorter control-row baseline.
                    baseline = KEY_BASELINE-CONTROL_HEIGHT+1 if row == 3 else 0
                    return glyph, dy+bounds[1]+baseline, max(advance, glyph.width+1)
        # Preserve display of prefilled text outside the on-screen alphabet.
        glyph = self._glyphs(character, face)
        bounds = face.getmask(character, mode='1').getbbox()
        dy = face.getbbox(character, anchor='ls')[1]+(bounds[1] if bounds else 0)
        return glyph, dy, max(advance, glyph.width+1)

    def password_text(self, text):
        """Draw precisely the same glyphs as the keys without scaling them."""
        field = Image.new('1', (self.width, PASSWORD_HEIGHT))
        draw = ImageDraw.Draw(field)
        offset = 0
        for char in text:
            glyph, dy, advance = self.password_character(char)
            draw.bitmap((PASSWORD_TEXT_X+round(offset), PASSWORD_BASELINE+dy), glyph, fill=1)
            offset += advance
        return field

    def password_window(self, state):
        """Keep the cursor visible without altering the full input value."""
        face = self.font(PASSWORD_FONT_SIZE, family='keyboard')
        start = min(state.window_start, state.cursor) if state.field_focused else 0
        available = self.width-PASSWORD_TEXT_X-5

        def width(value):
            return self.text_width(value, face)

        while start < state.cursor and width(state.value[start:state.cursor]) > available:
            start += 1
        end = state.cursor
        while end < len(state.value) and width(state.value[start:end+1]) <= available:
            end += 1
        state.window_start = start
        return state.value[start:end], face, start, end

    def keyboard_rectangles(self, grid):
        """Share key geometry with navigation; preview renderers may study variants."""
        return key_rectangles(grid, self.width, self.height)

    def keyboard(self, password, grid, cursor_row, cursor_col, hint='', shift=0,
                 state=None, cursor_visible=True):
        """Show QWERTY, shared password shortcuts and the focusable input strip."""
        image, draw = self.canvas()
        state = KeyboardState(password) if state is None else state
        text, face, start, end = self.password_window(state)
        image.paste(self.password_text(text), (0, 0))
        if start:
            draw.line((6, 3, 2, 7, 6, 11), fill=1)
        else:
            draw.ellipse((1, 3, 7, 9), outline=1)
            draw.line((7, 6, 12, 6), fill=1)
            draw.line((10, 6, 10, 9), fill=1)
        draw.rectangle((15, 3, 16, 4), fill=1)
        draw.rectangle((15, 8, 16, 9), fill=1)
        caret = min(self.width-5, PASSWORD_TEXT_X+round(self.text_width(state.value[start:state.cursor], face)))
        if cursor_visible:
            draw.line((caret, 1, caret, 12), fill=1, width=2 if state.field_focused else 1)
            if state.field_focused:
                draw.polygon(((caret-2, 0), (caret+2, 0), (caret, 2)), fill=1)
        if end < len(state.value):
            draw.line((self.width-3, 3, self.width-1, 7, self.width-3, 11), fill=1)
        for row, keys in enumerate(self.keyboard_rectangles(grid)):
            for col, (key, box) in enumerate(keys):
                if key is None:
                    continue
                x0, y0, x1, y1 = box
                active = not state.field_focused and row == cursor_row and col == cursor_col
                if active:
                    draw.rounded_rectangle(box, radius=1, fill=1)
                ink = 0 if active else 1
                cx, cy = (x0+x1)//2, (y0+y1)//2
                if key == SHIFT:
                    points = ((cx, cy-4), (cx+5, cy+1), (cx+2, cy+1),
                              (cx+2, cy+4), (cx-2, cy+4), (cx-2, cy+1), (cx-5, cy+1))
                    draw.polygon(points, outline=ink, fill=ink if shift else None)
                    if shift == 2:
                        draw.line((cx-3, cy+5, cx+3, cy+5), fill=ink)
                elif key == BACKSPACE:
                    draw.polygon(((cx-7, cy), (cx-3, cy-4), (cx+6, cy-4),
                                  (cx+6, cy+4), (cx-3, cy+4)), outline=ink)
                    draw.line((cx-1, cy-2, cx+3, cy+2), fill=ink)
                    draw.line((cx+3, cy-2, cx-1, cy+2), fill=ink)
                elif key == SPACE:
                    draw.line((x0+6, cy-1, x0+6, cy+1, x1-6, cy+1, x1-6, cy-1), fill=ink)
                elif key in (NUMBERS, LETTERS, SYMBOLS, SUBMIT):
                    text = {NUMBERS: '123', LETTERS: 'ABC', SYMBOLS: '#+=', SUBMIT: 'OK'}.get(key, key)
                    self.label(draw, box, text, 11, minimum=11, fill=ink)
                else:
                    glyphs, dx, dy = self.keyboard_glyph(key, x1-x0+1, y1-y0+1)
                    draw.bitmap(((x0+x1+1)//2+dx, y0+KEY_BASELINE+dy), glyphs, fill=ink)
        return image
