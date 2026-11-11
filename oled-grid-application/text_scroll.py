"""Time-based sequential scrolling for read-only OLED fields."""

import math

STEP_PIXELS = 2
STEP_SECONDS = 0.1
PAUSE_SECONDS = 1.4


class FieldScroller:
    """Reveal one overflowing value at a time without selecting or editing it."""

    def __init__(self, limits):
        self.limits = [max(0, int(value)) for value in limits]
        self.fields = []
        for index, maximum in enumerate(self.limits):
            if maximum:
                travel = math.ceil(maximum/STEP_PIXELS)*STEP_SECONDS
                self.fields.append((index, maximum, travel))
        self.duration = sum(travel+2*PAUSE_SECONDS for _, _, travel in self.fields)

    def offsets(self, elapsed):
        """Pause at both ends, then reset the value and advance to the next row."""
        values = [0]*len(self.limits)
        if not self.duration:
            return values
        elapsed = max(0, elapsed) % self.duration
        for index, maximum, travel in self.fields:
            duration = travel+2*PAUSE_SECONDS
            if elapsed < duration:
                steps = (int((elapsed-PAUSE_SECONDS)/STEP_SECONDS+1e-7)+1
                         if elapsed >= PAUSE_SECONDS else 0)
                values[index] = min(maximum, steps*STEP_PIXELS)
                return values
            elapsed -= duration
        return values
