"""Katana fire, driven by the streak multiplier.

  x1-x2  plain steel
  x3     HEATED: an orange heat glow along the blade, the tip half glowing like hot metal,
         a few embers drifting off it
  x4     ON FIRE: flames licking off the whole blade (they trail behind as you swing),
         red-orange glow, more embers
  x5     BLUE INFERNO: white-blue flames, bigger and denser, crackling sparks of electricity

All light is drawn additively (it glows) on a small layer covering just the blade area,
so it stays cheap. Intensity eases in when you level up and dies away when the streak breaks.
"""
import math
import random

import pygame

from . import config as C

FIRE = ((255, 245, 200), (255, 160, 50), (210, 50, 20))      # young -> old flame colours
BLUE = ((235, 250, 255), (90, 180, 255), (90, 60, 230))
LEVEL_COLOR = {3: (255, 140, 40), 4: (255, 90, 30), 5: (110, 190, 255)}
SPAWN = {3: 8.0, 4: 120.0, 5: 150.0}                          # particles per second


def _k(col, k):
    k = max(0.0, min(1.0, k))
    return (int(col[0] * k), int(col[1] * k), int(col[2] * k))


def _ramp(pal, u):
    """u = 1 (just born) .. 0 (about to die)."""
    a, b, c = pal
    if u > 0.55:
        v = (u - 0.55) / 0.45
        return tuple(int(m + (n - m) * v) for m, n in zip(b, a))
    v = u / 0.55
    return tuple(int(m + (n - m) * v) for m, n in zip(c, b))


class BladeFire:
    def __init__(self):
        self.level = 1
        self.power = 0.0          # 0..1 eased intensity of the current effect
        self.shown_level = 1      # the look being shown (keeps showing while it fades out)
        self.parts = []           # [x, y, vx, vy, life, max_life, size, palette, ember]
        self.spawn_acc = 0.0
        self.last = None
        self.layer = None
        if pygame.display.get_surface() is not None:     # make it now, not mid-game at x3
            self.layer = pygame.Surface((C.W, C.H)).convert()

    def set_level(self, level):
        self.level = level
        if level >= 3:
            self.shown_level = level

    def update_and_draw(self, surf, base, tip, now, visible=True):
        dt = 0.0 if self.last is None else min(0.05, now - self.last)
        self.last = now
        target = 1.0 if self.level >= 3 and visible else 0.0
        self.power += (target - self.power) * min(1.0, dt * (5.0 if target else 3.0))
        if self.power < 0.02 and not self.parts:
            self.power = 0.0
            return
        lvl = self.shown_level

        # spawn flames / embers along the blade
        bx, by = base
        tx, ty = tip
        if visible and self.power > 0.05:
            self.spawn_acc += SPAWN.get(lvl, 0) * dt * self.power
            pal = BLUE if lvl >= 5 else FIRE
            while self.spawn_acc >= 1.0:
                self.spawn_acc -= 1.0
                t = random.uniform(0.15, 1.0)
                x, y = bx + (tx - bx) * t, by + (ty - by) * t
                if lvl == 3 or random.random() < 0.12:          # ember: small, floats up slowly
                    self.parts.append([x, y, random.uniform(-30, 30), random.uniform(-90, -40),
                                       random.uniform(0.6, 1.1), 0, random.uniform(1.5, 2.8), pal, True])
                else:                                            # flame tongue
                    life = random.uniform(0.25, 0.5) * (1.15 if lvl >= 5 else 1.0)
                    size = random.uniform(9, 16) * (1.25 if lvl >= 5 else 1.0) * (0.6 + 0.6 * t)
                    self.parts.append([x, y, random.uniform(-30, 30), random.uniform(-190, -100),
                                       life, 0, size, pal, False])
                self.parts[-1][5] = self.parts[-1][4]

        # move
        alive = []
        for p in self.parts:
            p[4] -= dt
            if p[4] > 0:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[3] -= (60 if p[8] else 140) * dt               # flames accelerate upwards
                alive.append(p)
        self.parts = alive[-400:]

        # the area we draw into: blade + particles, padded
        xs = [bx, tx] + [p[0] for p in self.parts]
        ys = [by, ty] + [p[1] for p in self.parts]
        pad = 40
        box = pygame.Rect(int(min(xs)) - pad, int(min(ys)) - pad,
                          int(max(xs) - min(xs)) + 2 * pad, int(max(ys) - min(ys)) + 2 * pad)
        box = box.clip(surf.get_rect())
        if box.w <= 0 or box.h <= 0:
            return
        if self.layer is None:
            self.layer = pygame.Surface((C.W, C.H)).convert()
        L = self.layer
        L.fill((0, 0, 0), box)
        ox, oy = 0, 0
        pw = self.power
        col = LEVEL_COLOR.get(lvl, LEVEL_COLOR[3])
        flick = 0.85 + 0.15 * math.sin(now * 23) * math.sin(now * 7)

        if visible:
            # heat glow hugging the blade
            wide = {3: 16, 4: 24, 5: 28}.get(lvl, 16)
            glow_k = {3: 0.28, 4: 0.42, 5: 0.45}.get(lvl, 0.28)
            pygame.draw.line(L, _k(col, glow_k * pw * flick), base, tip, wide)
            pygame.draw.line(L, _k(col, (glow_k + 0.2) * pw * flick), base, tip, wide // 2)
            # hot metal: the tip half glows
            mid = (bx + (tx - bx) * 0.45, by + (ty - by) * 0.45)
            hot = (255, 200, 120) if lvl < 5 else (200, 240, 255)
            pygame.draw.line(L, _k(hot, (0.55 if lvl == 3 else 0.8) * pw), mid, tip, 4)
            pygame.draw.circle(L, _k(hot, 0.6 * pw * flick), tip, 6 + 3 * (lvl - 3))

        for p in self.parts:
            u = p[4] / p[5]
            c = _ramp(p[7], u)
            if p[8]:
                pygame.draw.circle(L, _k(c, 0.9 * u), (p[0] - ox, p[1] - oy), p[6])
            else:
                r = p[6] * (0.3 + 0.7 * u)               # a flame tongue: tall, pointing up
                stretch = 1.6 + 0.8 * (1 - u)
                outer = pygame.Rect(0, 0, r * 1.5, r * 1.5 * stretch)
                outer.midbottom = (p[0], p[1] + r * 0.6)
                inner = pygame.Rect(0, 0, r * 0.7, r * 0.7 * stretch)
                inner.midbottom = (p[0], p[1] + r * 0.45)
                pygame.draw.ellipse(L, _k(c, 0.45 * min(1.0, u * 1.5)), outer)
                pygame.draw.ellipse(L, _k(c, min(1.0, u * 1.6)), inner)

        if visible and lvl >= 5 and random.random() < 0.35 * pw:   # crackling electricity
            t = random.uniform(0.2, 1.0)
            x, y = bx + (tx - bx) * t, by + (ty - by) * t
            a = random.uniform(0, 2 * math.pi)
            pts = [(x, y)]
            for _ in range(4):
                a += random.uniform(-0.8, 0.8)
                x += math.cos(a) * random.uniform(7, 13)
                y += math.sin(a) * random.uniform(7, 13)
                pts.append((x, y))
            pygame.draw.lines(L, (210, 240, 255), False, pts, 2)

        surf.blit(L, box, area=box, special_flags=pygame.BLEND_ADD)

    def trail_color(self, steel):
        """The swoosh behind the blade takes on the fire colour."""
        if self.power <= 0:
            return steel
        col = LEVEL_COLOR.get(self.shown_level, steel)
        return tuple(int(s + (c - s) * self.power) for s, c in zip(steel, col))
