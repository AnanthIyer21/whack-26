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
TRAIL_FROM = 0.65     # trail covers the outer third of the blade


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
            k = _ease_out(self.anim)
            _blit_katana(surface, self.cur[0], self.cur[1], self.length, int(255 * min(1.0, self.anim * 1.6)),
                         0.88 + 0.12 * k)
            if self.anim < 1.0:   # soft light sweeping from guard to tip while drawing
                s = self.length * k
                g = tip(self.cur[0], self.cur[1], s)
                glow = _glow()
                glow.set_alpha(int(255 * (1 - self.anim * 0.6)))
                surface.blit(glow, glow.get_rect(center=(int(g[0]), int(g[1]))))
        elif self.fade > 0 and self.last_pose:
            base, angle, _ = self.last_pose
            _blit_katana(surface, base, angle, self.length, int(255 * self.fade), 1.0)

    def _draw_trail(self, surface):
        if len(self.trail) < 2:
            return
        L = self.length
        quads = []
        for (b0, a0, t0, _), (b1, a1, t1, s1) in zip(self.trail, self.trail[1:]):
            k = 1 - (self.clock - t1) / TRAIL_TIME
            if s1 < config.CUT_SPEED * 0.5 or k <= 0:
                continue
            quads.append((k, [tip(b0, a0, L * TRAIL_FROM), tip(b0, a0, L), tip(b1, a1, L), tip(b1, a1, L * TRAIL_FROM)],
                          [tip(b0, a0, L * 0.92), tip(b0, a0, L), tip(b1, a1, L), tip(b1, a1, L * 0.92)]))
        if not quads:
            return
        xs = [p[0] for _, q, _ in quads for p in q]
        ys = [p[1] for _, q, _ in quads for p in q]
        x0, y0 = int(min(xs)) - 2, int(min(ys)) - 2
        layer = pygame.Surface((int(max(xs)) - x0 + 4, int(max(ys)) - y0 + 4), pygame.SRCALPHA)
        for k, quad, core in quads:   # only as big as the trail itself: much cheaper than full screen
            pygame.draw.polygon(layer, (170, 225, 255, int(70 * k * k)), [(x - x0, y - y0) for x, y in quad])
            pygame.draw.polygon(layer, (240, 252, 255, int(230 * k)), [(x - x0, y - y0) for x, y in core])
        surface.blit(layer, (x0, y0))


_katana_cache = {}
_glow_cache = []


def _glow():
    if not _glow_cache:
        g = pygame.Surface((48, 48), pygame.SRCALPHA)
        for r in range(24, 0, -1):
            pygame.draw.circle(g, (255, 255, 255, int(200 * (1 - r / 24) ** 1.5)), (24, 24), r)
        _glow_cache.append(g)
    return _glow_cache[0]


def katana_sprite(L):
    """The katana drawn once at 2x and smooth-scaled, guard at the centre, blade pointing right."""
    L = int(L)
    if L not in _katana_cache:
        SS = 2
        hl = L * 0.3
        half_w = L + 12
        surf = pygame.Surface((int(2 * half_w * SS), 48 * SS), pygame.SRCALPHA)
        ox, oy = half_w * SS, 24 * SS

        def P(s, y):
            return (ox + s * SS, oy + y * SS)

        curve = L * 0.05
        back, edge = [], []
        for i in range(25):
            s = L * i / 24
            bend = -curve * (s / L) ** 2
            w = 5.5 - 1.5 * (s / L)
            back.append(P(s, bend - w))
            if s <= L * 0.9:
                edge.append(P(s, bend + w))
        tip_pt = P(L, -curve - 4)
        pygame.draw.polygon(surf, (110, 116, 132), back + [tip_pt] + edge[::-1])
        inner_back = [P(L * i / 24, -curve * (i / 24) ** 2 - 4) for i in range(23)]
        inner_edge = [P(s, -curve * (s / L) ** 2 + 4) for s in (L * 0.9 * i / 20 for i in range(21))]
        pygame.draw.polygon(surf, (200, 208, 222), inner_back + [P(L - 3, -curve - 3)] + inner_edge[::-1])
        pygame.draw.lines(surf, (250, 252, 255), False, inner_edge + [tip_pt], 2 * SS)        # bright edge
        pygame.draw.lines(surf, (160, 168, 185), False, [P(L * i / 24, -curve * (i / 24) ** 2 - 1) for i in range(22)], SS)
        pygame.draw.rect(surf, (215, 175, 65), (*P(0, -7), 10 * SS, 14 * SS))                  # habaki
        pygame.draw.ellipse(surf, (55, 40, 22), (*P(-6, -18), 7 * SS, 36 * SS))                  # tsuba
        pygame.draw.ellipse(surf, (195, 155, 65), (*P(-6, -18), 7 * SS, 36 * SS), SS * 2)
        pygame.draw.rect(surf, (30, 25, 35), (*P(-6 - hl, -6), hl * SS, 12 * SS), border_radius=4 * SS)
        for i in range(6):
            s0 = -9 - i * hl / 6.4
            pygame.draw.polygon(surf, (215, 205, 195), [P(s0, 0), P(s0 - hl / 13, -5), P(s0 - hl / 6.5, 0), P(s0 - hl / 13, 5)], SS)
        pygame.draw.circle(surf, (195, 155, 65), P(-8 - hl, 0), 6 * SS)
        _katana_cache[L] = pygame.transform.smoothscale(surf, (surf.get_width() // SS, surf.get_height() // SS))
    return _katana_cache[L]


def _blit_katana(surface, base, angle, L, alpha, scale):
    """Smoothly rotate the cached sprite around the guard and draw it at `base`."""
    img = pygame.transform.rotozoom(katana_sprite(L), -math.degrees(angle), scale)
    if alpha < 255:
        img.set_alpha(max(0, alpha))
    surface.blit(img, img.get_rect(center=(int(base[0]), int(base[1]))))
