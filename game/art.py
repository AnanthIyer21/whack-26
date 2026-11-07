"""Code-drawn art: fruit, cut halves, bomb, background. Made once at startup.

Everything is drawn at 2x and smooth-scaled down so the edges are anti-aliased.
If RB adds assets/fruit_<kind>.png it is used instead of the drawn fruit.
"""
import math
import random

import pygame

from game import assets, config

SS = 2  # supersampling factor

# inside colour of each fruit when cut, and its juice colour
FLESH = {
    "watermelon": (235, 55, 65), "orange": (255, 170, 40), "apple": (250, 240, 200),
    "banana": (250, 244, 205), "strawberry": (240, 90, 110), "golden": (255, 240, 150),
}
JUICE = {
    "watermelon": (220, 30, 50), "orange": (255, 150, 20), "apple": (230, 240, 150),
    "banana": (250, 230, 120), "strawberry": (220, 20, 60), "golden": (255, 215, 60),
}


def lerp(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def shaded_ball(s, c, R, dark, light, steps=None):
    """A sphere: concentric circles from a dark rim to a bright top-left highlight."""
    steps = steps or max(8, int(R // 2))
    for i in range(steps):
        k = i / steps
        r = R * (1 - k * 0.92)
        off = R * 0.32 * k
        pygame.draw.circle(s, lerp(dark, light, k), (c[0] - off, c[1] - off), r)


def _canvas(r):
    n = int((r * 2.6) * SS)
    return pygame.Surface((n, n), pygame.SRCALPHA), (n / 2, n / 2), r * SS


def _finish(s):
    w, h = s.get_size()
    return pygame.transform.smoothscale(s, (w // SS, h // SS))


def _watermelon(s, c, R):
    shaded_ball(s, c, R, (15, 70, 25), (110, 185, 80))
    for a in (0.25, 0.55, 0.85):
        w = R * 2 * a
        pygame.draw.ellipse(s, (20, 80, 25), (c[0] - w / 2, c[1] - R, w, 2 * R), int(R * 0.09))
    pygame.draw.circle(s, (170, 230, 150), (c[0] - R * 0.35, c[1] - R * 0.4), R * 0.14)


def _orange(s, c, R):
    shaded_ball(s, c, R, (190, 80, 5), (255, 190, 80))
    rng = random.Random(3)
    for _ in range(40):
        a, d = rng.uniform(0, math.tau), rng.uniform(0, 0.85) * R
        pygame.draw.circle(s, (215, 110, 15), (c[0] + math.cos(a) * d, c[1] + math.sin(a) * d), R * 0.035)
    pygame.draw.circle(s, (70, 120, 30), (c[0], c[1] - R * 0.88), R * 0.09)


def _apple(s, c, R):
    shaded_ball(s, c, R, (110, 5, 15), (245, 75, 70))
    pygame.draw.ellipse(s, (100, 10, 15), (c[0] - R * 0.18, c[1] - R * 0.98, R * 0.36, R * 0.2))
    pygame.draw.line(s, (90, 55, 25), (c[0], c[1] - R * 0.85), (c[0] + R * 0.12, c[1] - R * 1.25), int(R * 0.12))
    leaf = pygame.Surface((R * 0.8, R * 0.36), pygame.SRCALPHA)
    pygame.draw.ellipse(leaf, (70, 160, 50), leaf.get_rect())
    leaf = pygame.transform.rotate(leaf, 25)
    s.blit(leaf, leaf.get_rect(center=(c[0] + R * 0.42, c[1] - R * 1.08)))
    pygame.draw.circle(s, (255, 200, 200), (c[0] - R * 0.4, c[1] - R * 0.38), R * 0.13)


def _banana(s, c, R):
    outer, inner = [], []
    cy = c[1] + R * 0.95
    for i in range(25):
        a = math.radians(212 + 116 * i / 24)
        outer.append((c[0] + math.cos(a) * R * 1.3, cy + math.sin(a) * R * 1.32))
        inner.append((c[0] + math.cos(a) * R * 1.25, cy + math.sin(a) * R * 0.6))
    pygame.draw.polygon(s, (205, 165, 25), outer + inner[::-1])
    mid = [((o[0] + n[0]) / 2, (o[1] + n[1]) / 2 - R * 0.04) for o, n in zip(outer, inner)]
    pygame.draw.lines(s, (252, 228, 95), False, mid[2:-2], int(R * 0.22))
    pygame.draw.lines(s, (150, 110, 20), False, outer, int(R * 0.06))
    pygame.draw.circle(s, (90, 60, 20), outer[0], R * 0.1)
    pygame.draw.line(s, (110, 80, 30), outer[-1], (outer[-1][0] + R * 0.18, outer[-1][1] - R * 0.12), int(R * 0.12))


def _strawberry(s, c, R):
    pts = []
    for i in range(40):
        a = math.tau * i / 40
        x, y = math.sin(a), -math.cos(a)
        rad = R * (1.0 if y < 0 else 1.0 - 0.45 * y)  # narrower towards the bottom
        pts.append((c[0] + x * rad * (1 - 0.25 * max(0, y)), c[1] + y * rad * 1.1 + R * 0.1))
    pygame.draw.polygon(s, (180, 15, 35), pts)
    pygame.draw.ellipse(s, (235, 50, 70), (c[0] - R * 0.7, c[1] - R * 0.75, R * 1.1, R * 1.2))
    rng = random.Random(7)
    for _ in range(22):
        x, y = rng.uniform(-0.65, 0.65) * R, rng.uniform(-0.6, 0.8) * R
        if (x / R) ** 2 + ((y - 0.1 * R) / (1.05 * R)) ** 2 < 0.6:
            pygame.draw.ellipse(s, (250, 220, 110), (c[0] + x, c[1] + y, R * 0.07, R * 0.11))
    for k in range(5):
        a = math.radians(-90 + (k - 2) * 38)
        tip = (c[0] + math.cos(a) * R * 0.75, c[1] - R * 0.82 + math.sin(a) * R * 0.45 + R * 0.35)
        pygame.draw.polygon(s, (60, 150, 45), [(c[0] - R * 0.12, c[1] - R * 0.85),
                                                (c[0] + R * 0.12, c[1] - R * 0.85), tip])


def _golden(s, c, R):
    for i in range(6, 0, -1):
        pygame.draw.circle(s, (255, 220, 80, 18 * (7 - i)), c, R * (1 + i * 0.04))
    shaded_ball(s, c, R, (170, 120, 10), (255, 245, 170))
    for a in range(4):
        ang = a * math.pi / 2
        pygame.draw.line(s, (255, 255, 230), (c[0] - R * 0.3, c[1] - R * 0.35),
                         (c[0] - R * 0.3 + math.cos(ang) * R * 0.4, c[1] - R * 0.35 + math.sin(ang) * R * 0.4), int(R * 0.06))


def _bomb(s, c, R):
    shaded_ball(s, c, R, (10, 10, 14), (95, 95, 110))
    pygame.draw.rect(s, (110, 110, 120), (c[0] - R * 0.28, c[1] - R * 1.1, R * 0.56, R * 0.3), border_radius=int(R * 0.06))
    fuse = [(c[0], c[1] - R * 1.1), (c[0] + R * 0.15, c[1] - R * 1.35), (c[0] + R * 0.42, c[1] - R * 1.4)]
    pygame.draw.lines(s, (150, 110, 60), False, fuse, int(R * 0.1))
    # red X so it reads as danger at a glance
    for sx in (-1, 1):
        pygame.draw.line(s, (200, 30, 30), (c[0] - R * 0.35, c[1] - sx * R * 0.35),
                         (c[0] + R * 0.35, c[1] + sx * R * 0.35), int(R * 0.16))


DRAW = {"watermelon": _watermelon, "orange": _orange, "apple": _apple, "banana": _banana,
        "strawberry": _strawberry, "golden": _golden, "bomb": _bomb}
_sprites, _halves = {}, {}


def fruit_sprite(kind, r):
    if kind not in _sprites:
        img = assets.image(f"fruit_{kind}" if kind != "bomb" else "bomb", (int(r * 2.6), int(r * 2.6)))
        if img is None:
            s, c, R = _canvas(r)
            DRAW[kind](s, c, R)
            img = _finish(s)
        _sprites[kind] = img
    return _sprites[kind]


def half_sprites(kind, r):
    """(top, bottom) halves cut along the sprite's horizontal centre line, showing the inside."""
    if kind not in _halves:
        whole = fruit_sprite(kind, r)
        w, h = whole.get_size()
        out = []
        for top in (True, False):
            s = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
            s.blit(pygame.transform.smoothscale(whole, (w * SS, h * SS)), (0, 0))
            clear = pygame.Rect(0, h * SS / 2, w * SS, h * SS / 2) if top else pygame.Rect(0, 0, w * SS, h * SS / 2)
            s.fill((0, 0, 0, 0), clear)
            R, cx, cy = r * SS, w * SS / 2, h * SS / 2
            face = pygame.Rect(0, 0, R * 1.9, R * 0.5)
            face.center = (cx, cy)
            if kind == "watermelon":
                pygame.draw.ellipse(s, (60, 140, 50), face)
                pygame.draw.ellipse(s, (235, 240, 200), face.inflate(-R * 0.12, -R * 0.06))
            pygame.draw.ellipse(s, FLESH.get(kind, (240, 240, 220)), face.inflate(-R * 0.22, -R * 0.1))
            if kind == "watermelon":
                for i in range(-3, 4, 2):
                    pygame.draw.ellipse(s, (20, 15, 15), (cx + i * R * 0.18, cy - R * 0.04, R * 0.08, R * 0.12))
            elif kind == "orange":
                for i in range(6):
                    a = math.tau * i / 6
                    pygame.draw.line(s, (255, 220, 140), (cx, cy), (cx + math.cos(a) * R * 0.8, cy + math.sin(a) * R * 0.2), 3)
            out.append(_finish(s))
        _halves[kind] = tuple(out)
    return _halves[kind]


def make_background():
    """Dark wooden planks with grain and a darker vignette, drawn once."""
    img = assets.image("background", (config.WIDTH, config.HEIGHT))
    if img:
        return img.convert()
    W, H = config.WIDTH, config.HEIGHT
    bg = pygame.Surface((W, H))
    rng = random.Random(11)
    planks = 6
    pw = W / planks
    for i in range(planks):
        base = (70 + rng.randint(-8, 8), 44 + rng.randint(-6, 6), 26 + rng.randint(-4, 4))
        pygame.draw.rect(bg, base, (i * pw, 0, pw + 1, H))
        for _ in range(26):
            x = i * pw + rng.uniform(6, pw - 6)
            shade = lerp(base, (35, 20, 10) if rng.random() < 0.6 else (105, 70, 42), rng.uniform(0.2, 0.5))
            pts = [(x + math.sin(y / rng.uniform(40, 90) + rng.random()) * 3, y) for y in range(0, H + 20, 20)]
            pygame.draw.lines(bg, shade, False, pts, 1)
        pygame.draw.line(bg, (25, 14, 8), (i * pw, 0), (i * pw, H), 4)
    vignette = pygame.Surface((W, H), pygame.SRCALPHA)
    for k in range(40):
        a = int(110 * (1 - k / 40) ** 2)
        pygame.draw.rect(vignette, (0, 0, 0, a), (k * 8, k * 5, W - k * 16, H - k * 10), 8)
    bg.blit(vignette, (0, 0))
    return bg
