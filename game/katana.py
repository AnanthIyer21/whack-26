"""The katana sprite, drawn in code (replaced by RBadiadka7's sword.png later).

Built once, pointing straight up, at 3x size then smooth-scaled. The image is padded so the
point where the blade leaves the fist (the habaki) is exactly the image centre; that makes
rotating it around the fist a single rotozoom.

Parts, tip to handle: kissaki (angled tip), curved single-edged blade with a wavy hamon
(temper line) along the edge and a shinogi ridge, gold habaki collar, tsuba (guard),
tsuka (handle) with diamond ito wrapping, kashira (end cap).
"""
import math

import pygame

SS = 3
HALF_WIDTH = 7.0       # blade half-width at the collar, px (the fire glow uses these too)
CURVE = 0.05           # sori: how far the tip bends back, as a fraction of the blade length


def _k(col, f):
    return tuple(max(0, min(255, int(c * f))) for c in col)


def make_katana(blade_px, frozen=False):
    L = blade_px * SS
    handle = 0.30 * L
    w0 = HALF_WIDTH * SS           # blade half-width at the collar
    width = int(10 * w0)
    height = int(2 * L + 10 * SS)
    s = pygame.Surface((width, height), pygame.SRCALPHA)
    cx, py = width / 2, height / 2  # pivot: where the blade leaves the fist
    curve = CURVE * L               # sori: the blade bends back towards the tip

    steel = (150, 150, 155) if frozen else (175, 185, 200)
    polish = (175, 175, 180) if frozen else (232, 238, 248)
    ridge = (120, 120, 125) if frozen else (130, 140, 160)
    gold = (140, 140, 140) if frozen else (205, 165, 70)

    def spine(t):                   # centre of the blade at fraction t (0 collar .. 1 tip)
        return cx + curve * t * t, py - L * t

    def half_w(t):
        return w0 * (1 - 0.3 * t)

    N = 60
    back, edge, hamon = [], [], []
    for i in range(N + 1):
        t = i / N
        x, y = spine(t)
        w = half_w(t)
        kiss = 0.0 if t < 0.9 else (t - 0.9) / 0.1        # kissaki: edge sweeps up to the back
        e = w * (1 - kiss ** 1.6) if kiss else w
        back.append((x + w * (1 - 0.15 * kiss), y))
        edge.append((x - e, y))
        hw = 0.45 * w + 0.13 * w * math.sin(t * 46)        # wavy temper line
        hamon.append((x - e + min(hw, 2 * e) * (1 if e > 0 else 0), y))
    tip = (spine(1.0)[0] + w0 * 0.55, py - L)

    # blade body, polished edge band, ridge line, edge glint
    pygame.draw.polygon(s, steel, back + [tip] + edge[::-1])
    pygame.draw.polygon(s, polish, edge + hamon[::-1])
    ridge_pts = [(spine(i / N)[0] + 0.3 * half_w(i / N), spine(i / N)[1]) for i in range(0, int(N * 0.9))]
    pygame.draw.lines(s, ridge, False, ridge_pts, max(1, int(SS * 0.9)))
    pygame.draw.lines(s, (255, 255, 255) if not frozen else (200, 200, 200), False, edge[:int(N * 0.97)],
                      max(1, int(SS * 0.8)))
    yx, yy = spine(0.9)                                   # yokote: line where the tip starts
    pygame.draw.line(s, ridge, (yx - half_w(0.9), yy), (yx + half_w(0.9), yy), max(1, int(SS * 0.9)))
    pygame.draw.polygon(s, _k(steel, 0.75), [back[-1], tip, (tip[0] - 2 * SS, tip[1] + 3 * SS)])

    # habaki (gold collar)
    pygame.draw.rect(s, gold, pygame.Rect(cx - w0 * 1.25, py - 0.045 * L, w0 * 2.5, 0.045 * L + 2 * SS),
                     border_radius=int(SS * 1.5))
    # tsuba (guard), seen edge-on
    tsuba = pygame.Rect(0, 0, w0 * 6.4, 5.5 * SS)
    tsuba.center = (cx, py + 3.5 * SS)
    pygame.draw.ellipse(s, (30, 28, 32), tsuba)
    pygame.draw.ellipse(s, gold, tsuba, max(1, int(SS)))
    # tsuka (handle) with diamond wrapping
    top, bottom = py + 6.5 * SS, py + 6.5 * SS + handle
    hw = w0 * 1.15
    pygame.draw.rect(s, (25, 25, 30) if not frozen else (60, 60, 60),
                     pygame.Rect(cx - hw, top, 2 * hw, handle), border_radius=int(SS * 2))
    wrap = (215, 205, 185) if not frozen else (130, 130, 130)
    step = hw * 1.5
    y = top + step * 0.2
    while y + step < bottom - 4 * SS:
        pygame.draw.polygon(s, wrap, [(cx, y), (cx + hw * 0.75, y + step / 2), (cx, y + step),
                                      (cx - hw * 0.75, y + step / 2)])
        pygame.draw.polygon(s, (25, 25, 30), [(cx, y + step * 0.18), (cx + hw * 0.4, y + step / 2),
                                              (cx, y + step * 0.82), (cx - hw * 0.4, y + step / 2)])
        y += step
    pygame.draw.rect(s, gold, pygame.Rect(cx - hw * 1.08, bottom - 4 * SS, hw * 2.16, 6 * SS),
                     border_radius=int(SS * 2))           # kashira

    return pygame.transform.smoothscale(s, (width // SS, height // SS))


def angle_to_rotozoom(angle):
    """Blade direction (radians, screen coords) -> degrees for rotozoom of an up-pointing sprite."""
    return math.degrees(math.atan2(-math.cos(angle), -math.sin(angle)))
