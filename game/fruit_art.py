"""Placeholder fruit art, drawn in code until RBadiadka7's PNGs arrive.

Everything is drawn at 3x size and smooth-scaled down, which gives soft anti-aliased edges.
Each fruit: radial shading (light top-left, dark rim), its own details (stripes, seeds, crown),
and a proper cross-section "face" used on the two halves when it's cut.
"""
import math
import random

import pygame

SS = 3  # supersampling factor


def _lerp_col(a, b, u):
    u = max(0.0, min(1.0, u))
    return tuple(int(x + (y - x) * u) for x, y in zip(a, b))


def _shade(col, k):
    """k < 1 darker, k > 1 lighter."""
    if k < 1:
        return tuple(int(c * k) for c in col)
    return tuple(int(c + (255 - c) * (k - 1)) for c in col)


def _radial(size, center, radius, light, base, dark):
    """Opaque radial gradient: light at the centre, base midway, dark at the rim."""
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill((*dark, 255))
    n = 48
    for i in range(n):
        u = 1 - i / n                     # 1 = outside, 0 = centre
        col = _lerp_col(base, dark, (u - 0.55) / 0.45) if u > 0.55 else _lerp_col(light, base, u / 0.55)
        pygame.draw.circle(s, (*col, 255), center, max(1, radius * u))
    return s


def _clip(layer, mask):
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)


def _blend_draw(dst, fn):
    """Run a draw function on a temp layer and blend it on (so translucent colours mix)."""
    tmp = pygame.Surface(dst.get_size(), pygame.SRCALPHA)
    fn(tmp)
    dst.blit(tmp, (0, 0))


# ---------- silhouettes -------------------------------------------------------------------
def _ellipse_rect(c, rx, ry):
    return pygame.Rect(c[0] - rx, c[1] - ry, 2 * rx, 2 * ry)


def _banana_center(c, R, s):
    """Point on the banana's curved spine (s = 0 stem end .. 1 tip end) and its outward normal."""
    a = math.radians(145 - 110 * s)
    ox, oy = c[0], c[1] - 1.42 * R
    n = (math.cos(a), math.sin(a))
    return (ox + 1.6 * R * n[0], oy + 1.6 * R * n[1]), n


def _banana_half_thick(R, s):
    return max(0.035 * R, 0.25 * R * math.sin(math.pi * s) ** 0.55)


def _banana_poly(c, R):
    """Curved, fat in the middle, tapering to both ends."""
    outer, inner = [], []
    for i in range(41):
        s = i / 40
        (x, y), (nx, ny) = _banana_center(c, R, s)
        t = _banana_half_thick(R, s)
        outer.append((x + nx * t, y + ny * t))
        inner.append((x - nx * t * 0.85, y - ny * t * 0.85))
    return outer + inner[::-1]


def _strawberry_poly(c, R):
    pts = []
    for i in range(60):
        t = i / 60 * 2 * math.pi
        f = 0.55 + 0.45 * math.sqrt(max(0.0, (1 + math.cos(t)) / 2))
        pts.append((c[0] + 0.95 * R * math.sin(t) * f, c[1] - 0.9 * R * math.cos(t) + 0.05 * R))
    return pts


SHAPES = {   # rx, ry multipliers for the ellipse fruits
    "watermelon": (1.08, 0.9), "orange": (1.0, 1.0), "lemon": (1.08, 0.8), "apple": (0.98, 0.95),
    "kiwi": (1.06, 0.86), "pineapple": (0.8, 1.0),
}


def _silhouette(surf, name, c, R, col):
    if name == "banana":
        pygame.draw.polygon(surf, col, _banana_poly(c, R))
    elif name == "strawberry":
        pygame.draw.polygon(surf, col, _strawberry_poly(c, R))
    else:
        rx, ry = SHAPES[name]
        pygame.draw.ellipse(surf, col, _ellipse_rect(c, rx * R, ry * R))
        if name == "lemon":   # little nubs at both ends
            pygame.draw.circle(surf, col, (c[0] - rx * R * 0.97, c[1]), R * 0.16)
            pygame.draw.circle(surf, col, (c[0] + rx * R * 0.97, c[1]), R * 0.16)


def face_geometry(name, R):
    """Vertical centre offset and half-height of the fruit along its middle (where it's cut)."""
    if name == "banana":
        return 0.18 * R, 0.23 * R, 0.15 * R
    if name == "strawberry":
        return 0.05 * R, 0.9 * R, 0.34 * R
    rx, ry = SHAPES[name]
    return 0.0, ry * R * 0.97, 0.36 * rx * R


# ---------- details on the skin -----------------------------------------------------------
def _details(surf, name, c, R, rng):
    cx, cy = c
    if name == "watermelon":
        for k in (-0.8, -0.4, 0.0, 0.4, 0.8):
            pts = [(cx + k * R * 1.08 + math.sin(j * 0.9) * R * 0.06, cy - R + j * R * 0.1) for j in range(21)]
            pygame.draw.lines(surf, (20, 80, 30), False, pts, int(R * 0.14))
    elif name == "orange" or name == "lemon":
        dot = (205, 110, 20) if name == "orange" else (215, 190, 30)
        for _ in range(int(R * 1.2)):
            a, d = rng.uniform(0, 6.28), rng.uniform(0, 0.95) * R
            pygame.draw.circle(surf, dot, (cx + math.cos(a) * d, cy + math.sin(a) * d * 0.9), SS * 0.8)
    elif name == "kiwi":
        for _ in range(int(R * 2)):
            a, d = rng.uniform(0, 6.28), rng.uniform(0, 1.0) * R
            pygame.draw.circle(surf, (95, 65, 35), (cx + math.cos(a) * d, cy + math.sin(a) * d * 0.86), SS * 0.7)
    elif name == "pineapple":
        col = (150, 105, 25)
        for k in range(-6, 7):
            x = cx + k * R * 0.28
            pygame.draw.line(surf, col, (x - R, cy - R), (x + R, cy + R), int(SS * 2))
            pygame.draw.line(surf, col, (x + R, cy - R), (x - R, cy + R), int(SS * 2))
        for k in range(-6, 7):
            for j in range(-6, 7):
                pygame.draw.circle(surf, (120, 80, 20), (cx + k * R * 0.28, cy + j * R * 0.28), SS * 1.4)
    elif name == "strawberry":
        for i in range(26):
            t = i * 2.399
            d = math.sqrt((i + 0.5) / 26) * 0.75 * R
            x, y = cx + math.cos(t) * d * 0.9, cy + math.sin(t) * d + 0.05 * R
            pygame.draw.ellipse(surf, (255, 225, 120), (x - SS * 1.2, y - SS * 2, SS * 2.4, SS * 4))
    elif name == "banana":
        for off, col in ((0.4, (225, 190, 40)), (-0.35, (232, 200, 55))):     # the ridges along it
            pts = []
            for i in range(4, 37):
                (x, y), (nx, ny) = _banana_center(c, R, i / 40)
                t = _banana_half_thick(R, i / 40) * off
                pts.append((x + nx * t, y + ny * t))
            pygame.draw.lines(surf, col, False, pts, int(SS * 1.6))
        for s_, o in ((0.3, 0.2), (0.55, -0.3), (0.62, 0.35), (0.75, 0.0)):  # a few ripe spots
            (x, y), (nx, ny) = _banana_center(c, R, s_)
            pygame.draw.circle(surf, (150, 110, 40), (x + nx * o * 0.25 * R, y + ny * o * 0.25 * R), SS * 1.6)


def _extras(surf, name, c, R):
    cx, cy = c
    if name == "apple":
        pygame.draw.line(surf, (90, 60, 30), (cx, cy - 0.85 * R), (cx + 0.08 * R, cy - 1.2 * R), int(SS * 3))
        leaf = pygame.Surface((int(R * 0.6), int(R * 0.28)), pygame.SRCALPHA)
        pygame.draw.ellipse(leaf, (70, 160, 60), leaf.get_rect())
        leaf = pygame.transform.rotate(leaf, 25)
        surf.blit(leaf, leaf.get_rect(center=(cx + 0.32 * R, cy - 1.05 * R)))
    elif name == "orange":
        pygame.draw.circle(surf, (70, 130, 40), (cx + 0.1 * R, cy - 0.93 * R), R * 0.09)
    elif name == "lemon":
        pygame.draw.circle(surf, (160, 170, 40), (cx + 1.12 * R, cy), R * 0.07)
    elif name == "strawberry":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = 0.5 * R if i % 2 == 0 else 0.16 * R
            pts.append((cx + math.cos(a) * rr * 1.1, cy - 0.78 * R + math.sin(a) * rr * 0.5))
        pygame.draw.polygon(surf, (50, 140, 50), pts)
        pygame.draw.line(surf, (50, 120, 40), (cx, cy - 0.8 * R), (cx, cy - 1.05 * R), int(SS * 3))
    elif name == "pineapple":
        for i, (ang, ln) in enumerate([(-90, 0.95), (-65, 0.8), (-115, 0.8), (-42, 0.6), (-138, 0.6)]):
            a = math.radians(ang)
            base = (cx, cy - 0.92 * R)
            tip = (base[0] + math.cos(a) * ln * R, base[1] + math.sin(a) * ln * R)
            nx, ny = -math.sin(a) * 0.11 * R, math.cos(a) * 0.11 * R
            col = (40, 120, 45) if i % 2 == 0 else (60, 150, 60)
            pygame.draw.polygon(surf, col, [(base[0] + nx, base[1] + ny), tip, (base[0] - nx, base[1] - ny)])
    elif name == "banana":
        (x0, y0), _ = _banana_center(c, R, 0.0)
        (x1, y1), _ = _banana_center(c, R, 0.05)
        dx, dy = x0 - x1, y0 - y1
        d = math.hypot(dx, dy)
        dx, dy = dx / d, dy / d
        end = (x0 + dx * 0.32 * R, y0 + dy * 0.32 * R)
        pygame.draw.line(surf, (125, 140, 60), (x0, y0), end, int(0.13 * R))   # stem
        pygame.draw.circle(surf, (85, 70, 35), end, 0.075 * R)
        (tx, ty), _ = _banana_center(c, R, 1.0)
        pygame.draw.circle(surf, (70, 50, 25), (tx, ty), 0.06 * R)                # dark tip


# ---------- the cut face ------------------------------------------------------------------
def _face(surf, name, c, rx, ry, rng):
    def ell(s, col, dx=0.0):
        pygame.draw.ellipse(surf, col, _ellipse_rect((c[0] + dx * rx, c[1]), rx * s, ry * s))

    def ring_dots(n, rad, col, size, angle_off=0.0):
        for i in range(n):
            a = angle_off + i * 2 * math.pi / n
            x, y = c[0] + math.cos(a) * rx * rad, c[1] + math.sin(a) * ry * rad
            pygame.draw.ellipse(surf, col, (x - size * 0.6, y - size, size * 1.2, size * 2))

    def segments(n, col, inner):
        for i in range(n):
            a = i * 2 * math.pi / n
            pygame.draw.line(surf, col, c, (c[0] + math.cos(a) * rx * inner, c[1] + math.sin(a) * ry * inner),
                             int(SS * 1.5))

    if name == "watermelon":
        ell(1.0, (30, 110, 40)); ell(0.9, (205, 235, 190)); ell(0.82, (230, 55, 70)); ell(0.5, (245, 95, 105))
        ring_dots(8, 0.5, (30, 20, 20), SS * 2.2)
    elif name in ("orange", "lemon"):
        peel, pith, flesh = (((240, 130, 25), (255, 238, 210), (255, 170, 50)) if name == "orange"
                             else ((240, 215, 40), (255, 250, 225), (250, 235, 110)))
        ell(1.0, peel); ell(0.9, pith); ell(0.84, flesh); ell(0.5, _shade(flesh, 1.15))
        segments(9, pith, 0.84); ell(0.12, pith)
    elif name == "apple":
        ell(1.0, (195, 35, 35)); ell(0.93, (250, 242, 210)); ell(0.38, (240, 225, 180))
        ring_dots(5, 0.18, (100, 60, 30), SS * 1.8, 0.3)
    elif name == "kiwi":
        ell(1.0, (120, 85, 45)); ell(0.93, (105, 180, 45)); ell(0.68, (140, 205, 70)); ell(0.3, (240, 240, 205))
        ring_dots(18, 0.43, (25, 25, 20), SS * 1.1)
    elif name == "strawberry":
        ell(1.0, (215, 30, 50)); ell(0.86, (245, 105, 115)); ell(0.5, (255, 205, 205))
    elif name == "banana":
        ell(1.0, (235, 205, 55)); ell(0.8, (250, 245, 212)); ell(0.2, (220, 210, 170))
    elif name == "pineapple":
        ell(1.0, (185, 135, 35)); ell(0.9, (250, 220, 90)); ell(0.55, (255, 232, 130)); ell(0.25, (255, 245, 190))


# ---------- public builders ---------------------------------------------------------------
def _pad(name, r):
    return int(r * {"pineapple": 0.9, "banana": 0.85}.get(name, 0.45)) + 4


def _build_big(kind):
    """Whole fruit at SS scale. Returns (surface, centre, R)."""
    r = kind.radius
    pad = _pad(kind.name, r)
    D = (2 * (r + pad)) * SS
    c = (D / 2, D / 2)
    R = r * SS
    rng = random.Random(kind.name)

    mask = pygame.Surface((D, D), pygame.SRCALPHA)
    mask.fill((255, 255, 255, 0))
    _silhouette(mask, kind.name, c, R, (255, 255, 255, 255))

    hl = (c[0] - 0.35 * R, c[1] - 0.4 * R)
    body = _radial((D, D), hl, 1.75 * R, _shade(kind.skin, 1.35), kind.skin, _shade(kind.skin, 0.55))
    _details(body, kind.name, c, R, rng)
    hx, hy = (c[0] - 0.25 * R, c[1] + 0.12 * R) if kind.name == "banana" else (c[0] - 0.38 * R, c[1] - 0.42 * R)
    _blend_draw(body, lambda s: pygame.draw.ellipse(       # specular highlight, clipped to the body
        s, (255, 255, 255, 85), _ellipse_rect((hx, hy), 0.26 * R, 0.13 * R if kind.name == "banana" else 0.17 * R)))
    _clip(body, mask)

    out = pygame.Surface((D, D), pygame.SRCALPHA)
    out.blit(body, (0, 0))
    _extras(out, kind.name, c, R)            # stems, leaves, crown, tips
    return out, c, R


def make_whole(kind):
    big, _, _ = _build_big(kind)
    w = big.get_width() // SS
    return pygame.transform.smoothscale(big, (w, w))


def make_half(kind, side):
    """side -1 keeps the left part, +1 the right. The cut is the vertical line through the centre,
    and the half shows the full cross-section face (like a half tilted towards you)."""
    big, c, R = _build_big(kind)
    D = big.get_width()
    if side < 0:
        big.fill((0, 0, 0, 0), pygame.Rect(int(c[0]), 0, D, D))
    else:
        big.fill((0, 0, 0, 0), pygame.Rect(0, 0, int(c[0]), D))
    dy, half_h, face_rx = face_geometry(kind.name, R)
    _face(big, kind.name, (c[0], c[1] + dy), face_rx, half_h, random.Random(kind.name + "f"))
    w = D // SS
    return pygame.transform.smoothscale(big, (w, w))


def make_splat(kind):
    """A juice splash shape in the fruit's juice colour (opaque; faded with set_alpha)."""
    r = kind.radius
    D = 4 * r * 2
    s = pygame.Surface((D, D), pygame.SRCALPHA)
    c = (D / 2, D / 2)
    col = (*_shade(kind.juice, 1.1), 255)
    rng = random.Random(kind.name + "splat")
    for _ in range(6):
        a, d = rng.uniform(0, 6.28), rng.uniform(0, 0.35) * r * 2
        pygame.draw.circle(s, col, (c[0] + math.cos(a) * d, c[1] + math.sin(a) * d), rng.uniform(0.35, 0.55) * r * 2)
    for _ in range(10):
        a, d = rng.uniform(0, 6.28), rng.uniform(1.0, 1.7) * r * 2
        pygame.draw.circle(s, col, (c[0] + math.cos(a) * d, c[1] + math.sin(a) * d), rng.uniform(0.05, 0.14) * r * 2)
    return pygame.transform.smoothscale(s, (D // 2, D // 2))
