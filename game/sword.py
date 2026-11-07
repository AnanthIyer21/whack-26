"""The sword: keeps the last blade sample, works out tip speed, sends draw/sheathe.

Step 2 draws a plain line; the katana, draw animation and trail come in the polish step.
"""
import math

import pygame

from game import bridge, config
from game.slicing import tip


class Sword:
    def __init__(self):
        self.length = bridge.BLADE_LENGTH * config.HEIGHT
        self.prev = None          # last valid (base, angle, t) used for cut checks
        self.cur = None           # current (base, angle, t)
        self.speed = 0.0          # tip speed in px/s between the last two samples
        self.drawn = False        # what the rival has been told
        self.sheathed_since = None
        self.active = False

    def reset_history(self):
        """Forget the previous sample so the next move can't create a giant slash."""
        self.prev = None
        self.speed = 0.0

    def update(self, sample, now):
        """Returns a list of event dicts (sword_drawn / sword_sheathed)."""
        events = []
        if sample.active and sample.visible:
            if not self.active:
                self.reset_history()                 # fresh draw: no history
            self.active = True
            self.sheathed_since = None
            if not self.drawn:
                self.drawn = True
                events.append({"type": "sword_drawn"})
            if sample.new:
                if self.cur and sample.t - self.cur[2] <= config.SAMPLE_GAP_RESET:
                    self.prev = self.cur
                else:
                    self.prev = None
                self.cur = (sample.base, sample.angle, sample.t)
                if self.prev:
                    gap = max(1e-4, self.cur[2] - self.prev[2])
                    t0 = tip(self.prev[0], self.prev[1], self.length)
                    t1 = tip(self.cur[0], self.cur[1], self.length)
                    self.speed = math.dist(t0, t1) / gap
                else:
                    self.speed = 0.0
        else:
            if self.active:
                self.reset_history()
                self.cur = None
            self.active = False
            if self.drawn:
                if self.sheathed_since is None:
                    self.sheathed_since = now
                elif now - self.sheathed_since >= config.SHEATHE_DEBOUNCE:
                    self.drawn = False
                    events.append({"type": "sword_sheathed"})
        return events

    def sweep(self):
        """(base0, ang0, base1, ang1) to test this frame, or None if no fresh fast move."""
        if not (self.active and self.prev and self.cur):
            return None
        sweep = (self.prev[0], self.prev[1], self.cur[0], self.cur[1])
        self.prev = None  # each pair of samples is tested once
        return sweep

    def draw(self, surface):
        if not (self.active and self.cur):
            return
        base, angle, _ = self.cur
        t = tip(base, angle, self.length)
        pygame.draw.line(surface, (210, 220, 235), base, t, 6)
        pygame.draw.circle(surface, config.GOLD, (int(base[0]), int(base[1])), 9)
