"""The bomb explosion sequence, which also clears the screen.

  0.00 - 0.45 s  WIND-UP: the world freezes, the screen darkens, light rays burst out of the
                 bomb and grow, the bomb swells and trembles.   (game timer doesn't tick)
  0.45 s         BOOM: white flash, fireball, two shockwave rings, shake, fire + smoke, and
                 every fruit/half/bomb on screen is blasted outward, charred, and fades away.
                 Blasted fruit score nothing and are NOT misses. Spawning pauses for ~1 s.
"""
import math
import random

import pygame

from . import config as C
from .entities import Particle, blit_rotated

WINDUP = 0.45
AFTER = 0.75


class Debris:
    """Something blown away by the blast: charred, spinning, fading."""
    LIFE = 0.9

    def __init__(self, img, x, y, rot, bx, by):
        self.img = img.copy()
        self.img.fill((140, 110, 95), special_flags=pygame.BLEND_RGB_MULT)   # scorched
        dx, dy = x - bx, y - by
        d = math.hypot(dx, dy) or 1.0
        sp = random.uniform(1000, 1500) * max(0.6, 1.2 - d / 900)   # closer = harder
        self.x, self.y = x, y
        self.vx, self.vy = dx / d * sp, dy / d * sp - 250
        self.rot = rot
        self.spin = random.choice((-1, 1)) * random.uniform(400, 800)
        self.age = 0.0

    def step(self, dt):
        self.age += dt
        self.vy += 700 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.spin * dt
        return self.age < self.LIFE

    def draw(self, surf, off):
        u = self.age / self.LIFE
        blit_rotated(surf, self.img, (self.x, self.y), self.rot, off, alpha=int(255 * (1 - u * u)), cache=False)


class BombBlast:
    def __init__(self, bomb):
        self.x, self.y = bomb.x, bomb.y
        self.bomb_img = bomb.image()
        self.rot = bomb.rot
        self.age = 0.0
        self.boomed = False
        self.ray_angles = [random.uniform(0, 2 * math.pi) for _ in range(11)]
        self.ray_widths = [random.uniform(0.04, 0.09) for _ in range(11)]

    @property
    def winding_up(self):
        return self.age < WINDUP

    @property
    def done(self):
        return self.age >= WINDUP + AFTER

    def step(self, dt):
        """Returns True on the frame the bomb goes off."""
        self.age += dt
        if not self.boomed and self.age >= WINDUP:
            self.boomed = True
            return True
        return False

    def boom_particles(self):
        parts = []
        for _ in range(70):                       # fire
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(200, 900)
            col = random.choice([(255, 240, 180), (255, 190, 70), (255, 120, 40), (240, 70, 30)])
            parts.append(Particle(self.x, self.y, math.cos(a) * sp, math.sin(a) * sp,
                                  random.uniform(0.35, 0.8), col, random.uniform(4, 10), g=250.0, drag=2.0))
        for _ in range(18):                       # smoke, rising
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(60, 260)
            g = random.randint(70, 110)
            parts.append(Particle(self.x, self.y, math.cos(a) * sp, math.sin(a) * sp,
                                  random.uniform(0.8, 1.3), (g, g, g + 5), random.uniform(14, 26), g=-90.0, drag=2.5))
        return parts

    def draw(self, screen, glow, dark, off):
        """Light (rays, fireball, rings) is drawn on an additive layer: colours add up like
        real light instead of greying the scene."""
        add = _add_layer()
        add.fill((0, 0, 0))
        x, y = self.x + off[0], self.y + off[1]
        if self.winding_up:
            u = self.age / WINDUP
            dark.set_alpha(int(110 * u))
            screen.blit(dark, (0, 0))
            L = 60 + 1500 * u * u
            for a0, w in zip(self.ray_angles, self.ray_widths):
                a = a0 + self.age * 0.8
                for wk, col, k in ((1.0, (255, 200, 120), 0.25 + 0.35 * u), (0.35, (255, 245, 220), 0.4 + 0.6 * u)):
                    p1 = (x + math.cos(a - w * wk) * L, y + math.sin(a - w * wk) * L)
                    p2 = (x + math.cos(a + w * wk) * L, y + math.sin(a + w * wk) * L)
                    pygame.draw.polygon(add, _k(col, k), [(x, y), p1, p2])
            _soft_glow(add, (x, y), 50 + 60 * u, (255, 210, 140), 0.5 + 0.5 * u)
            screen.blit(add, (0, 0), special_flags=pygame.BLEND_ADD)
            jit = 4 * u
            img = pygame.transform.rotozoom(self.bomb_img, self.rot, 1 + 0.35 * u)
            screen.blit(img, img.get_rect(center=(x + random.uniform(-jit, jit), y + random.uniform(-jit, jit))))
            return

        a = self.age - WINDUP
        if a < 0.35:                               # fireball
            v = a / 0.35
            _soft_glow(add, (x, y), 60 + 190 * (1 - (1 - v) ** 2), (255, 170, 70), (1 - v) ** 1.5)
        for delay, col, wmax in ((0.0, (255, 255, 255), 22), (0.08, (255, 160, 70), 12)):   # shockwaves
            t = a - delay
            if 0 <= t < 0.55:
                v = t / 0.55
                r = 60 + 1400 * (1 - (1 - v) ** 3)
                pygame.draw.circle(add, _k(col, 0.9 * (1 - v)), (x, y), r, max(2, int(wmax * (1 - v))))
        screen.blit(add, (0, 0), special_flags=pygame.BLEND_ADD)


_ADD = None


def _add_layer():
    global _ADD
    if _ADD is None:
        _ADD = pygame.Surface((C.W, C.H)).convert()
    return _ADD


def _k(col, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(c * k) for c in col)


def _soft_glow(add, center, R, col, strength):
    """Radial glow: dim coloured edge to a bright white-hot core, in 16 smooth steps."""
    n = 16
    for i in range(n):
        f = i / (n - 1)                            # 0 = outer edge, 1 = core
        c = tuple(int(a + (255 - a) * f * f) for a in col)
        pygame.draw.circle(add, _k(c, strength * (0.15 + 0.85 * f ** 1.5)), center, max(1, R * (1 - 0.92 * f)))
