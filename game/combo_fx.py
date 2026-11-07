"""Combo effects.

While a swing is going: a thin CHAIN of light links the fruit cut in this swing, and from
3 fruit a small live counter ("x3", "x4"...) follows the latest cut.
When the swing ends, the effect scales with the combo (see on_cut below); SAVAGE (5+) also
triggers a short slow motion (the play scene reads .time_scale).
"""
import math
import random

import pygame

from . import config as C
from .boom import _add_layer, _k
from .scoring import tier_for


class ComboFX:
    def __init__(self, app):
        self.app = app
        self.chain = []            # cut positions in the current swing
        self.chain_color = (255, 255, 255)
        self.chain_fade = 0.0      # > 0 while a finished chain fades out
        self.fade_k = 0.5
        self.fading_chain = []
        self.counter = None        # (n, pos, t_shown, color)
        self.banners = []          # dicts: combo, pos, t
        self.rings = []            # (x, y, t, color, strength)
        self.slowmo = 0.0          # seconds of slow motion left (real time)

    # ---- events from the play scene ------------------------------------------------------
    # Effects scale with the combo so small ones stay low-key:
    #   2 fruit       just a faint, thin flicker of light linking the two (no text)
    #   NICE/GREAT    live counter from 3, a medium banner, a small ring, no rays
    #   SAVAGE+ (5+)  big banner with soft rays, a bigger ring, short slow motion
    def on_cut(self, pos, swing_n, now):
        self.chain.append(pos)
        tier = tier_for(swing_n)          # None below 3 fruit
        if swing_n == 2:
            self.chain_color = (200, 225, 255)
        if tier:
            self.chain_color = tier.color
            if swing_n >= 3:
                self.counter = (swing_n, pos, now, tier.color)

    def on_swing_end(self, combo, now):
        """combo: scoring.Combo or None (single cut)."""
        if combo and combo.n >= 3 and len(self.chain) >= 2:
            self.fading_chain, self.chain_fade, self.fade_k = list(self.chain), 0.35, 0.5
        elif len(self.chain) == 2:              # a double: a quiet flicker, nothing else
            self.fading_chain, self.chain_fade, self.fade_k = list(self.chain), 0.35, 0.22
        last = self.chain[-1] if self.chain else (C.W / 2, C.H / 2)
        self.chain = []
        self.counter = None
        if not combo:
            return
        x, y = last
        style = "mid" if combo.n < 5 else "big"
        pos = (max(240, min(C.W - 240, x)), max(170, min(C.H - 150, y - 70)))
        self.banners.append({"combo": combo, "pos": pos, "t": now, "style": style})
        self.rings.append((x, y, now, combo.color, 0.35 if style == "mid" else 0.7))
        if style == "big":
            self.slowmo = 0.4

    def update(self, dt, now):
        self.slowmo = max(0.0, self.slowmo - dt)
        self.chain_fade = max(0.0, self.chain_fade - dt)
        self.banners = [b for b in self.banners if now - b["t"] < 1.25]
        self.rings = [r for r in self.rings if now - r[2] < 0.45]

    @property
    def time_scale(self):
        return 0.35 if self.slowmo > 0 else 1.0

    # ---- drawing ---------------------------------------------------------------------
    def draw(self, screen, now):
        add = _add_layer()
        add.fill((0, 0, 0))
        used = False

        if len(self.chain) >= 2:
            k = 0.18 if len(self.chain) == 2 else (0.5 if len(self.chain) < 5 else 0.8)
            self._lightning(add, self.chain, self.chain_color, k, now)
            used = True
        if self.chain_fade > 0 and len(self.fading_chain) >= 2:
            self._lightning(add, self.fading_chain, self.chain_color, self.fade_k * self.chain_fade / 0.35, now)
            used = True
        for x, y, t, col, k in self.rings:
            u = (now - t) / 0.45
            r = 25 + 220 * k * (1 - (1 - u) ** 3)
            pygame.draw.circle(add, _k(col, 0.6 * (1 - u)), (x, y), r, max(2, int(8 * k * (1 - u)) + 1))
            used = True
        for b in self.banners:                       # soft rays, only for the big ones
            age = now - b["t"]
            if b["style"] == "big" and age < 0.8:
                c = b["combo"]
                u = age / 0.8
                bx, by = b["pos"]
                n_rays = 14
                L = 220 + 30 * min(c.n, 8)
                for i in range(n_rays):
                    a = i * 2 * math.pi / n_rays + age * 1.2
                    w = 0.05
                    p1 = (bx + math.cos(a - w) * L, by + math.sin(a - w) * L * 0.55)
                    p2 = (bx + math.cos(a + w) * L, by + math.sin(a + w) * L * 0.55)
                    pygame.draw.polygon(add, _k(c.color, 0.18 * (1 - u) ** 1.5), [(bx, by), p1, p2])
                used = True
        if used:
            screen.blit(add, (0, 0), special_flags=pygame.BLEND_ADD)

        if self.counter:                             # live "x3" counter (from 3 fruit)
            n, (x, y), t, col = self.counter
            pop = 1 + 0.35 * max(0.0, 1 - (now - t) / 0.12)
            self._text(screen, f"x{n}", int(44 * pop), col, (x + 36, y - 52), 0)

        for b in self.banners:
            c = b["combo"]
            age = now - b["t"]
            bx, by = b["pos"]
            big = b["style"] == "big"
            if age < 0.1:
                scale = (1.5 if big else 1.25) - (5 if big else 2.5) * age
            else:
                scale = 1.0
            alpha = 255 if age < 0.9 else int(255 * (1 - (age - 0.9) / 0.35))
            size = int(((64 + 6 * min(c.n - 5, 4)) if big else (44 + 4 * c.n)) * scale)
            if big:
                self._text(screen, c.name + "!", size, c.color, (bx, by), -5, alpha)
                self._text(screen, f"{c.n} fruit", max(10, int(38 * scale)), (255, 255, 255),
                           (bx + 6, by + size * 0.7), -5, alpha)
            else:
                self._text(screen, f"{c.name}!", size, c.color, (bx, by), -4, alpha)

    def _lightning(self, add, pts, col, strength, now):
        rng = random.Random(int(now * 30))           # re-crackles 30 times a second
        path = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            dx, dy = x1 - x0, y1 - y0
            d = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / d, dx / d
            for i in range(1, 5):
                u = i / 5
                j = rng.uniform(-1, 1) * min(28.0, d * 0.12)
                path.append((x0 + dx * u + nx * j, y0 + dy * u + ny * j))
            path.append((x1, y1))
        pygame.draw.lines(add, _k(col, 0.3 * strength), False, path, 7)
        pygame.draw.lines(add, _k(col, 0.8 * strength), False, path, 3)
        pygame.draw.lines(add, _k((255, 255, 255), 0.8 * strength), False, path, 1)
        for p in pts:
            pygame.draw.circle(add, _k(col, 0.8 * strength), p, 5)

    def _text(self, screen, s, size, col, center, angle=0, alpha=255):
        app = self.app
        img = app.font(size).render(s, True, col)
        sh = app.font(size).render(s, True, (0, 0, 0))
        if angle:
            img = pygame.transform.rotozoom(img, angle, 1.0)
            sh = pygame.transform.rotozoom(sh, angle, 1.0)
        img.set_alpha(alpha)
        sh.set_alpha(int(alpha * 0.55))
        r = img.get_rect(center=center)
        screen.blit(sh, r.move(3, 4))
        screen.blit(img, r)
