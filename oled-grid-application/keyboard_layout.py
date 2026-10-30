"""Phone-style password keyboard state and shared pixel geometry."""

SHIFT = '<shift>'
BACKSPACE = '<backspace>'
SPACE = '<space>'
SUBMIT = '<ok>'
NUMBERS = '<123>'
LETTERS = '<abc>'
SYMBOLS = '<symbols>'
PASSWORD_HEIGHT = 14
PASSWORD_FONT_SIZE = 15
PASSWORD_BASELINE = 11
PASSWORD_TEXT_X = 20
CONTROL_HEIGHT = 8
KEY_BASELINE = 11

FOOTER = (NUMBERS, '.', SPACE, '_', SUBMIT)
ALPHABET = (tuple('qwertyuiop'), tuple('asdfghjkl'),
            (SHIFT,)+tuple('zxcvbnm')+(BACKSPACE,), FOOTER)
DIGITS = (tuple('1234567890'), tuple('@#$%&-+()/'),
          (SYMBOLS,)+tuple('*"\':;!?')+(BACKSPACE,), (LETTERS,)+FOOTER[1:])
PUNCTUATION = (tuple('[]{}<>^|~`'), tuple(',=\\')+(None,)*6,
               (NUMBERS,)+(None,)*7+(BACKSPACE,), (LETTERS,)+FOOTER[1:])


def key_rectangles(rows, width=128, height=64):
    """Keep the familiar four rows while reserving a readable input strip."""
    letter_height = (height-PASSWORD_HEIGHT-CONTROL_HEIGHT)//3
    result = []
    for row, keys in enumerate(rows):
        top = PASSWORD_HEIGHT+row*letter_height if row < 3 else height-CONTROL_HEIGHT
        bottom = top+letter_height-1 if row < 3 else height-1
        margin = 6 if row == 1 and len(keys) == 9 else 0
        if row == 3:
            weights = (25, 16, 46, 16, 25)
        elif row == 2:
            weights = (2,)+(1,)*7+(2,)
        else:
            weights = (1,)*len(keys)
        total, offset = sum(weights), 0
        boxes = []
        for key, weight in zip(keys, weights):
            left = margin+round(offset*(width-2*margin)/total)
            offset += weight
            right = margin+round(offset*(width-2*margin)/total)-1
            boxes.append((key, (left, top, right, bottom)))
        result.append(tuple(boxes))
    return tuple(result)


class KeyboardState:
    """Keep input text separate from the horizontally scrolled display window."""

    def __init__(self, initial=''):
        self.value = str(initial)
        self.cursor = len(self.value)
        self.window_start = 0
        self.field_focused = False
        self.mode = 'letters'
        self.shift = 0  # 0: lower case, 1: next letter, 2: caps lock
        self.row = self.col = 0

    @property
    def rows(self):
        """Show direct ABC/123/symbol controls instead of cycling whole alphabets."""
        if self.mode == 'numbers':
            return DIGITS
        if self.mode == 'symbols':
            return PUNCTUATION
        if self.shift:
            return tuple(tuple(key.upper() if key is not None and len(key) == 1 else key for key in row)
                         for row in ALPHABET)
        return ALPHABET

    def move(self, direction):
        """Map vertical movement by key centers across rows of different widths."""
        if self.field_focused:
            if direction == 'left':
                self.cursor = max(0, self.cursor-1)
            elif direction == 'right':
                self.cursor = min(len(self.value), self.cursor+1)
            elif direction == 'down':
                self.field_focused = False
            return
        if direction == 'up' and self.row == 0:
            self.field_focused = True
            return
        rows = self.rows
        if direction in ('left', 'right'):
            step = -1 if direction == 'left' else 1
            col = self.col+step
            while 0 <= col < len(rows[self.row]):
                if rows[self.row][col] is not None:
                    self.col = col
                    break
                col += step
        else:
            target = self.row+(-1 if direction == 'up' else 1)
            if not 0 <= target < len(rows):
                return
            rectangles = key_rectangles(rows)
            current = rectangles[self.row][self.col][1]
            center = current[0]+current[2]
            self.col = min((col for col, key in enumerate(rows[target]) if key is not None),
                           key=lambda col: abs(sum(rectangles[target][col][1][::2])-center))
            self.row = target

    def activate(self):
        """Apply a key; only an explicit OK submits the full, untrimmed value."""
        if self.field_focused:
            self.field_focused = False
            return False
        key = self.rows[self.row][self.col]
        if key is None:
            return False
        if key == SHIFT:
            self.shift = (self.shift+1) % 3
            return False
        if key in (NUMBERS, LETTERS, SYMBOLS):
            self.mode = {NUMBERS: 'numbers', LETTERS: 'letters', SYMBOLS: 'symbols'}[key]
            if self.shift == 1:
                self.shift = 0
        elif key == BACKSPACE:
            if self.cursor:
                self.value = self.value[:self.cursor-1]+self.value[self.cursor:]
                self.cursor -= 1
        elif key == SPACE:
            self.value = self.value[:self.cursor]+' '+self.value[self.cursor:]
            self.cursor += 1
        elif key == SUBMIT:
            return True
        else:
            self.value = self.value[:self.cursor]+key+self.value[self.cursor:]
            self.cursor += 1
            if self.shift == 1:
                self.shift = 0
        return False
