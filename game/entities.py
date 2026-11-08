"""Things that fly: fruit, bombs, fruit halves, juice droplets, slash streaks and splats.

Sprites are built once (game/fruit_art.py, until RBadiadka7's PNGs arrive) and rotated each
frame with rotozoom (smooth edges). Positions are screen pixels; velocities px/s.
"""
from collections import deque
from dataclasses import dataclass
import math
import random

import pygame

from . import config as C
from . import fruit_art as art


@dataclass(frozen=True)
class Kind:
    name: str
    radius: int
    skin: tuple
    flesh: tuple
    juice: tuple


KINDS = [
    Kind("watermelon", 56, (45, 135, 50), (230, 60, 70), (230, 50, 70)),
    Kind("pineapple", 50, (215, 165, 45), (250, 225, 95), (250, 215, 80)),
    Kind("orange", 40, (248, 145, 30), (255, 185, 70), (255, 155, 35)),
    Kind("banana", 40, (248, 222, 70), (250, 245, 205), (250, 235, 160)),
    Kind("apple", 38, (205, 35, 40), (250, 240, 205), (250, 235, 190)),
    Kind("lemon", 36, (250, 228, 60), (255, 250, 175), (250, 240, 110)),
    Kind("kiwi", 32, (135, 95, 55), (125, 195, 60), (140, 210, 70)),
    Kind("strawberry", 28, (220, 30, 50), (250, 125, 135), (235, 45, 70)),
]
KIND_BY_NAME = {k.name: k for k in KINDS}
BOMB_RADIUS = 36


# ---------- sprites -----------------------------------------------------------------------
_cache = {}


def sprite(key, maker):
    if key not in _cache:
        # convert_alpha: store in the screen's pixel format so every blit/rotate is fast
        _cache[key] = maker().convert_alpha()
    return _cache[key]


def _bomb_sprite():
    SS = art.SS
    r = BOMB_RADIUS
    D = (2 * r + 30) * SS
    c = (D / 2, D / 2 + 6 * SS)
    R = r * SS
    mask = pygame.Surface((D, D), pygame.SRCALPHA)
    mask.fill((255, 255, 255, 0))
    pygame.draw.circle(mask, (255, 255, 255, 255), c, R)
    body = art._radial((D, D), (c[0] - 0.35 * R, c[1] - 0.4 * R), 1.7 * R, (90, 90, 105), (35, 35, 45), (10, 10, 14))
    art._clip(body, mask)
    out = pygame.Surface((D, D), pygame.SRCALPHA)
    # fuse: a little curved rope out of the cap
    fuse = [(c[0] + math.sin(i * 0.5) * 4 * SS, c[1] - R - i * 2.2 * SS) for i in range(7)]
    pygame.draw.lines(out, (150, 120, 80), False, fuse, int(4 * SS))
    out.blit(body, (0, 0))
    pygame.draw.circle(out, (200, 40, 40), c, R, int(3 * SS))          # red danger ring
    pygame.draw.rect(out, (120, 120, 130), (c[0] - 8 * SS, c[1] - R - 4 * SS, 16 * SS, 10 * SS),
                     border_radius=int(3 * SS))
    art._blend_draw(out, lambda s: pygame.draw.ellipse(
        s, (255, 255, 255, 90), art._ellipse_rect((c[0] - 0.38 * R, c[1] - 0.42 * R), 0.25 * R, 0.16 * R)))
    w = D // SS
    return pygame.transform.smoothscale(out, (w, w))


def prewarm():
    """Build every sprite up front so the first cut of each fruit doesn't stutter."""
    for k in KINDS:
        sprite(("fruit", k.name), lambda k=k: art.make_whole(k))
        for side in (-1, 1):
            sprite(("half", k.name, side), lambda k=k, side=side: art.make_half(k, side))
        sprite(("splat", k.name), lambda k=k: art.make_splat(k))
    sprite("bomb", _bomb_sprite)


_rot_cache = {}
ROT_STEP = 3   # degrees: spinning fruit reuse cached rotations instead of rotating every frame


def blit_rotated(surf, img, pos, angle_deg, offset=(0, 0), alpha=None, cache=True):
    if cache:
        q = int(round(angle_deg / ROT_STEP)) % (360 // ROT_STEP)
        key = (id(img), q)
        rot = _rot_cache.get(key)
        if rot is None:
            if len(_rot_cache) > 2500:
                _rot_cache.clear()
            rot = _rot_cache[key] = pygame.transform.rotozoom(img, q * ROT_STEP, 1.0)
    else:
        rot = pygame.transform.rotozoom(img, angle_deg, 1.0)
    if alpha is not None:
        if cache:
            rot = rot.copy()      # never change the alpha of a shared cached image
        rot.set_alpha(alpha)
    surf.blit(rot, rot.get_rect(center=(pos[0] + offset[0], pos[1] + offset[1])))


# ---------- flying things -----------------------------------------------------------------
class Flyer:
    """Something thrown up from below with gravity and spin."""

    def __init__(self, pos, vel, gravity, spin):
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.g = gravity
        self.rot = random.uniform(-25, 25)
        self.spin = spin
        self.dead = False
        self.cut = False
        self.hist = deque(maxlen=100)   # (time, x, y) over the last ~1.5 s, for lag cuts

    def remember(self, now):
        self.hist.append((now, self.x, self.y))

    def pos_at(self, t):
        """Where this was at time t (interpolated); current position if t is newer than the log."""
        h = self.hist
        if not h or t >= h[-1][0]:
            return self.x, self.y
        if t <= h[0][0]:
            return h[0][1], h[0][2]
        lo, hi = 0, len(h) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if h[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        t0, x0, y0 = h[lo]
        t1, x1, y1 = h[hi]
        u = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
        return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u

    def step(self, dt):
        self.vy += self.g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.spin * dt

    def fell_off(self, r):
        return self.vy > 0 and self.y - r * 1.6 > C.H + 10


class Fruit(Flyer):
    is_bomb = False

    def __init__(self, kind, pos, vel, gravity, spin):
        super().__init__(pos, vel, gravity, spin * 0.6)
        self.kind = kind
        self.radius = kind.radius

    def image(self):
        return sprite(("fruit", self.kind.name), lambda: art.make_whole(self.kind))

    def draw(self, surf, off):
        blit_rotated(surf, self.image(), (self.x, self.y), self.rot, off)


class Bomb(Flyer):
    is_bomb = True

    def __init__(self, pos, vel, gravity, spin):
        super().__init__(pos, vel, gravity, spin * 0.3)
        self.radius = BOMB_RADIUS
        self.hit_radius = BOMB_RADIUS * 0.85   # a little forgiving

    def image(self):
        return sprite("bomb", _bomb_sprite)

    def draw(self, surf, off, glow=None, now=0.0):
        blit_rotated(surf, self.image(), (self.x, self.y), self.rot, off)
        # fizzing spark at the end of the fuse (follows the rotation)
        a = math.radians(self.rot + 90)
        d = self.radius + 16
        fx = self.x + math.cos(a) * d + off[0]
        fy = self.y - math.sin(a) * d + off[1] + 6
        flick = 4 + 2.5 * math.sin(now * 40 + self.x)
        target = glow if glow is not None else surf
        pygame.draw.circle(target, (255, 170, 60, 140), (fx, fy), flick + 5)
        pygame.draw.circle(target, (255, 240, 200, 255), (fx, fy), flick * 0.6 + 1)


class Half(Flyer):
    def __init__(self, kind, side, pos, vel, gravity, rot, spin):
        super().__init__(pos, vel, gravity, spin)
        self.kind, self.side, self.rot = kind, side, rot

    def image(self):
        return sprite(("half", self.kind.name, self.side), lambda: art.make_half(self.kind, self.side))

    def draw(self, surf, off):
        blit_rotated(surf, self.image(), (self.x, self.y), self.rot, off)


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "g", "drag")

    def __init__(self, x, y, vx, vy, life, color, size, g=900.0, drag=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.g, self.drag = color, size, g, drag

    def step(self, dt):
        if self.drag:
            k = max(0.0, 1 - self.drag * dt)
            self.vx *= k
            self.vy *= k
        self.vy += self.g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, layer, off):
        u = self.life / self.max_life
        pygame.draw.circle(layer, (*self.color, int(235 * min(1.0, u * 1.6))),
                           (self.x + off[0], self.y + off[1]), max(1.0, self.size * (0.35 + 0.65 * u)))


class SlashMark:
    """A thin bright streak across the fruit along the cut, gone in a blink."""
    LIFE = 0.14

    def __init__(self, x, y, direction, length):
        self.x, self.y, self.d, self.len, self.age = x, y, direction, length, 0.0

    def step(self, dt):
        self.age += dt
        return self.age < self.LIFE

    def draw(self, layer, off):
        u = 1 - self.age / self.LIFE
        dx, dy = self.d
        L = self.len * (0.7 + 0.5 * (1 - u))      # stretches a little as it fades
        a = (self.x - dx * L / 2 + off[0], self.y - dy * L / 2 + off[1])
        b = (self.x + dx * L / 2 + off[0], self.y + dy * L / 2 + off[1])
        pygame.draw.line(layer, (255, 255, 255, int(110 * u)), a, b, max(1, int(9 * u)))
        pygame.draw.line(layer, (255, 255, 255, int(255 * u)), a, b, max(1, int(3 * u)))


class Splat:
    """Juice stain on the 'screen glass': one clean splash shape, fading out."""
    LIFE = 1.1

    def __init__(self, x, y, kind):
        self.x, self.y, self.age = x, y, 0.0
        base = sprite(("splat", kind.name), lambda: art.make_splat(kind))
        self.img = pygame.transform.rotozoom(base, random.uniform(0, 360), random.uniform(0.85, 1.1))

    def step(self, dt):
        self.age += dt
        return self.age < self.LIFE

    def draw(self, surf, off):
        u = self.age / self.LIFE
        self.img.set_alpha(int(120 * (1 - u * u)))
        surf.blit(self.img, self.img.get_rect(center=(self.x + off[0], self.y + off[1])))


# ---------- reactions ---------------------------------------------------------------------
def slice_fruit(fruit: Fruit, blade_angle, motion):
    """Split a fruit along the BLADE's line at the moment of contact.

    The halves separate across that line; juice sprays along the swing (motion) direction.
    Returns (halves, particles, splat, slash).
    """
    cx, cy = math.cos(blade_angle), math.sin(blade_angle)   # cut line direction
    mx, my = motion
    rot = math.degrees(math.atan2(cx, cy))          # rotates the sprite's vertical cut line onto it
    # the sprite's local "left" after that rotation, in screen coords (perpendicular to the cut)
    nlx, nly = -math.cos(math.radians(rot)), math.sin(math.radians(rot))
    k = fruit.kind
    halves = []
    for side in (-1, 1):
        sx, sy = nlx * side, nly * side
        halves.append(Half(k, side, (fruit.x, fruit.y),     # start exactly where the fruit was
                           (fruit.vx * 0.7 + sx * 120 + mx * 50, fruit.vy * 0.6 + sy * 120 + my * 50),
                           fruit.g, rot, side * random.uniform(70, 140)))
    parts = []
    swing = math.atan2(my, mx)
    for i in range(14):                              # droplets in a cone along the swing
        a = swing + random.uniform(-0.9, 0.9)
        sp = random.uniform(160, 460)
        parts.append(Particle(fruit.x, fruit.y, math.cos(a) * sp, math.sin(a) * sp,
                              random.uniform(0.3, 0.55), k.juice, random.uniform(2.5, 5.0), g=1100.0, drag=1.5))
    for i in range(8):                               # a small even burst all round
        a = i * math.pi / 4 + random.uniform(-0.2, 0.2)
        sp = random.uniform(90, 160)
        parts.append(Particle(fruit.x, fruit.y, math.cos(a) * sp, math.sin(a) * sp,
                              0.25, k.juice, 3.0, g=400.0, drag=3.0))
    slash = SlashMark(fruit.x, fruit.y, (cx, cy), k.radius * 2.8)
    return halves, parts, Splat(fruit.x, fruit.y, k), slash


def explode_bomb(bomb: Bomb):
    parts = []
    for _ in range(60):
        a = random.uniform(0, 2 * math.pi)
        sp = random.uniform(150, 750)
        col = random.choice([(255, 220, 120), (255, 140, 40), (255, 80, 30), (90, 90, 90)])
        parts.append(Particle(bomb.x, bomb.y, math.cos(a) * sp, math.sin(a) * sp,
                              random.uniform(0.4, 0.9), col, random.uniform(4, 10), g=300.0, drag=1.0))
    return parts
