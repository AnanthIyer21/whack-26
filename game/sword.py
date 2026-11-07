"""The katana: tracks blade samples, tip speed, draw/fade animation, the glowing trail.

Cutting is only allowed once the draw animation has finished, and the blade history is
cleared on every interruption so a jump can never become a screen-wide slash.
"""
import math

import pygame

from game import bridge, config
from game.slicing import tip

DRAW_TIME = 0.12
FADE_TIME = 0.15
TRAIL_TIME = 0.14
TRAIL_FROM = 0.45     # trail covers the blade from 45% of its length to the tip


def _ease_out(k):
    return 1 - (1 - k) ** 3


class Sword:
    def __init__(self):
        self.length = bridge.BLADE_LENGTH * config.HEIGHT
        self.prev = None          # last valid (base, angle, t) used for cut checks
        self.cur = None           # current (base, angle, t)
        self.speed = 0.0          # tip speed in px/s between the last two samples
        self.drawn = False        # what the rival has been told
        self.sheathed_since = None
        self.active = False
        self.anim = 0.0           # 0..1 draw progress
        self.fade = 0.0           # 1 -> 0 while fading out
        self.last_pose = None     # pose shown while fading
        self.trail = []           # [(base, angle, t, speed)]
        self.clock = 0.0

    def reset_history(self):
        """Forget the previous sample and the trail so the next move can't create a giant slash."""
        self.prev = None
        self.speed = 0.0
        self.trail.clear()

    @property
    def ready(self):
        return self.active and self.anim >= 1.0

    def update(self, sample, now, dt):
        """Returns a list of event dicts (sword_drawn / sword_sheathed)."""
        events = []
        self.clock += dt
        if sample.active and sample.visible:
            if not self.active:
                self.reset_history()
                self.cur = None
                self.anim = 0.0
                self.fade = 0.0
            self.active = True
            self.anim = min(1.0, self.anim + dt / DRAW_TIME)
            self.sheathed_since = None
            if not self.drawn:
                self.drawn = True
                events.append({"type": "sword_drawn"})
            if sample.new:
                if self.cur and sample.t - self.cur[2] <= config.SAMPLE_GAP_RESET:
                    self.prev = self.cur
                else:
                    self.prev = None
                    self.trail.clear()
                self.cur = (sample.base, sample.angle, sample.t)
                if self.prev:
                    gap = max(1e-4, self.cur[2] - self.prev[2])
                    self.speed = math.dist(tip(self.prev[0], self.prev[1], self.length),
                                           tip(self.cur[0], self.cur[1], self.length)) / gap
                else:
                    self.speed = 0.0
                self.trail.append((self.cur[0], self.cur[1], self.clock, self.speed))
        else:
            if self.active:
                self.last_pose = self.cur
                self.fade = 1.0 if self.cur else 0.0
                self.reset_history()
                self.cur = None
            self.active = False
            self.fade = max(0.0, self.fade - dt / FADE_TIME)
            if self.drawn:
                if self.sheathed_since is None:
                    self.sheathed_since = now
                elif now - self.sheathed_since >= config.SHEATHE_DEBOUNCE:
                    self.drawn = False
                    events.append({"type": "sword_sheathed"})
        self.trail = [p for p in self.trail if self.clock - p[2] <= TRAIL_TIME]
        return events

    def sweep(self):
        """(base0, ang0, base1, ang1) to test this frame, or None if there's no fresh move."""
        if not (self.ready and self.prev and self.cur):
            return None
        sweep = (self.prev[0], self.prev[1], self.cur[0], self.cur[1])
        self.prev = None  # each pair of samples is tested once
        return sweep

    # ---------------- drawing ----------------
    def draw(self, surface):
        self._draw_trail(surface)
        if self.active and self.cur:
            _draw_katana(surface, self.cur[0], self.cur[1], self.length, _ease_out(self.anim), 255,
                         glint=self.anim < 1.0)
        elif self.fade > 0 and self.last_pose:
            base, angle, _ = self.last_pose
            _draw_katana(surface, base, angle, self.length, 1.0, int(255 * self.fade))

    def _draw_trail(self, surface):
        if len(self.trail) < 2:
            return
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        L = self.length
        for (b0, a0, t0, _), (b1, a1, t1, s1) in zip(self.trail, self.trail[1:]):
            if s1 < config.CUT_SPEED * 0.5:
                continue
            k = 1 - (self.clock - t1) / TRAIL_TIME
            if k <= 0:
                continue
            quad = [tip(b0, a0, L * TRAIL_FROM), tip(b0, a0, L), tip(b1, a1, L), tip(b1, a1, L * TRAIL_FROM)]
            pygame.draw.polygon(layer, (150, 215, 255, int(55 * k * k)), quad)
            core = [tip(b0, a0, L * 0.88), tip(b0, a0, L), tip(b1, a1, L), tip(b1, a1, L * 0.88)]
            pygame.draw.polygon(layer, (240, 252, 255, int(230 * k)), core)
        surface.blit(layer, (0, 0))


def _draw_katana(surface, base, angle, L, extend, alpha, glint=False):
    """Katana with the guard at `base`, blade along `angle`, hilt behind the fist."""
    ca, sa = math.cos(angle), math.sin(angle)
    pad = L * 0.45
    size = int(2 * (L + pad))
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    ox, oy = size / 2, size / 2

    def P(s, y):  # blade-local (along, across) -> layer coords
        return (ox + s * ca - y * sa, oy + s * sa + y * ca)

    bl = L * extend
    curve = L * 0.05
    back, edge = [], []
    for i in range(13):
        s = bl * i / 12
        bend = -curve * (s / L) ** 2
        w = 5.5 - 1.5 * (s / L)
        back.append(P(s, bend - w))
        if s <= bl * 0.9:
            edge.append(P(s, bend + w))
    tip_pt = P(bl, -curve * (bl / L) ** 2 - 4)
    blade = back + [tip_pt] + edge[::-1]
    if bl > 4:
        pygame.draw.polygon(layer, (196, 204, 218), blade)
        pygame.draw.aalines(layer, (110, 116, 132), True, blade)
        pygame.draw.aalines(layer, (250, 252, 255), False, edge + [tip_pt])           # bright cutting edge
        pygame.draw.aalines(layer, (150, 158, 175), False, [P(s, -curve * (s / L) ** 2 - 1)
                                                            for s in (bl * k / 8 for k in range(9))])
    # habaki (gold collar), tsuba (guard), hilt with diamond wrap, end cap
    pygame.draw.polygon(layer, (210, 170, 60), [P(0, -7), P(10, -7), P(10, 7), P(0, 7)])
    pygame.draw.polygon(layer, (60, 45, 25), [P(-6, -17), P(0, -17), P(0, 17), P(-6, 17)])
    pygame.draw.polygon(layer, (190, 150, 60), [P(-6, -17), P(0, -17), P(0, 17), P(-6, 17)], 2)
    hl = L * 0.3
    pygame.draw.polygon(layer, (30, 25, 35), [P(-6, -7), P(-6 - hl, -6), P(-6 - hl, 6), P(-6, 7)])
    for i in range(6):
        s0 = -10 - i * hl / 6
        pygame.draw.polygon(layer, (210, 200, 190), [P(s0, 0), P(s0 - hl / 12, -5), P(s0 - hl / 6, 0), P(s0 - hl / 12, 5)], 1)
    pygame.draw.circle(layer, (190, 150, 60), P(-8 - hl, 0), 6)
    if glint and bl > 4:
        g = P(bl * 0.95, 0)
        pygame.draw.circle(layer, (255, 255, 255), g, 7)
        pygame.draw.line(layer, (255, 255, 255), (g[0] - 14, g[1]), (g[0] + 14, g[1]), 2)
        pygame.draw.line(layer, (255, 255, 255), (g[0], g[1] - 14), (g[0], g[1] + 14), 2)
    if alpha < 255:
        layer.set_alpha(alpha)
    surface.blit(layer, (base[0] - ox, base[1] - oy))
