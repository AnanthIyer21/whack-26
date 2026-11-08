"""Katana fire, driven by the streak multiplier.

  x1-x2  plain steel
  x3     HEATED: a soft heat aura hugging the blade, hottest towards the tip (like metal
         fresh from the forge), and the odd spark flicking off it
  x4     ON FIRE: flame tongues rising off the blade - white-hot at the root, orange, then
         deep red as they curl up and fade - trailing behind as you swing, plus sparks
  x5     BLUE FLAME: the same, but white -> cyan -> violet, a little bigger and denser,
         with fine arcs of electricity now and then

How it looks clean: every bit of light is a pre-rendered SOFT sprite (smooth falloff, no hard
edges), and everything is added together like real light (additive blending) on a small layer
covering just the blade area. Flames are teardrop sprites (pointed at the top); colour and
brightness come from a few pre-built steps so nothing is computed per pixel at run time.
Intensity eases in when you level up and dies away when the streak breaks.
"""
import math
import random

import numpy as np
import pygame

from . import config as C
from . import katana as KAT

# flame colour through its life: young (root) -> mid -> old (tip of the tongue)
FIRE = ((255, 248, 220), (255, 165, 45), (245, 70, 20))
BLUE = ((240, 252, 255), (80, 195, 255), (120, 80, 255))
AURA = {3: (255, 120, 35), 4: (255, 85, 25), 5: (80, 170, 255)}
TRAIL = {3: (255, 150, 60), 4: (255, 100, 40), 5: (120, 200, 255)}
SPAWN = {3: 0.0, 4: 115.0, 5: 130.0}        # flame tongues per second
SPARKS = {3: 6.0, 4: 10.0, 5: 12.0}         # sparks per second
STAGES = 6                                  # colour steps through a flame's life
LEVELS = 5                                  # brightness steps (for fading)


# ---------- soft sprites (built once, cached) ------------------------------------------------
_cache = {}


def _to_surface(arr):
    """float array (h, w, 3) in 0..255 -> opaque surface (black = no light)."""
    surf = pygame.surfarray.make_surface(np.ascontiguousarray(arr.clip(0, 255).astype(np.uint8).transpose(1, 0, 2)))
    return surf.convert() if pygame.display.get_surface() is not None else surf


def _flame_shape(w, h):
    """Teardrop intensity 0..1: round at the bottom, drawn to a point at the top."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    yn = (ys - h * 0.62) / (h * 0.5)                # 0 at the fat part, negative going up
    xn = (xs - (w - 1) / 2) / (w / 2)
    width = np.where(yn < 0, 1.0 + yn * 0.85, 1.0 - yn * 0.15)   # narrows upwards to a point
    width = np.clip(width, 0.05, 1.0)
    d = np.sqrt((xn / width) ** 2 + yn ** 2)
    return np.clip(1.0 - d, 0.0, 1.0) ** 1.6


def _dot_shape(r):
    ys, xs = np.mgrid[0:2 * r, 0:2 * r].astype(np.float32)
    d = np.hypot(xs - r + 0.5, ys - r + 0.5) / r
    return np.clip(1.0 - d, 0.0, 1.0) ** 2.2


def _ramp(pal, u):
    """u = 1 (young) .. 0 (old)."""
    a, b, c = pal
    if u > 0.5:
        v = (u - 0.5) / 0.5
        return tuple(m + (n - m) * v for m, n in zip(b, a))
    v = u / 0.5
    return tuple(m + (n - m) * v for m, n in zip(c, b))


def flame_sprite(pal_key, size_i, stage, level):
    """size_i 0..3, stage 0 (young) .. STAGES-1 (old), level 1..LEVELS brightness."""
    key = ("flame", pal_key, size_i, stage, level)
    s = _cache.get(key)
    if s is None:
        pal = BLUE if pal_key == "blue" else FIRE
        w = 10 + 5 * size_i
        h = int(w * 2.1)
        shape = _flame_shape(w, h)
        u = 1.0 - stage / (STAGES - 1)
        col = np.array(_ramp(pal, u), np.float32)
        core = np.array(pal[0], np.float32)
        # a white-hot core in the fat part of the young flames
        hot = (shape ** 3) * (0.6 * u)
        rgb = shape[..., None] * col * (1 - hot[..., None]) + hot[..., None] * core
        s = _cache[key] = _to_surface(rgb * (level / LEVELS))
    return s


def dot_sprite(col, r, level):
    key = ("dot", col, r, level)
    s = _cache.get(key)
    if s is None:
        s = _cache[key] = _to_surface(_dot_shape(r)[..., None] * np.array(col, np.float32) * (level / LEVELS))
    return s


def aura_sprite(lvl, length, level):
    """Soft glow that follows the katana's real shape: its curve (sori), its taper and its
    angled tip. Built pointing UP with the blade base at the centre - the same layout as the
    katana sprite - so it's rotated and placed exactly like the sword itself."""
    length = int(length)
    key = ("aura", lvl, length, level)
    s = _cache.get(key)
    if s is None:
        pad = {3: 14, 4: 18, 5: 20}[lvl]
        hw0, curve = KAT.HALF_WIDTH, KAT.CURVE * length
        W2 = int(pad + hw0 + curve + 4)
        H2 = int(length + pad + 4)
        ys, xs = np.mgrid[0:2 * H2, 0:2 * W2].astype(np.float32)
        X = xs - W2 + 0.5                       # + = the blade's back (the way it curves)
        Y = ys - H2 + 0.5                       # up the blade is negative
        t = -Y / length                         # 0 at the collar .. 1 at the tip
        tc = np.clip(t, 0, 1)
        spine = curve * tc ** 2
        hw = hw0 * (1 - 0.3 * tc)
        kiss = np.clip((tc - 0.9) / 0.1, 0, 1)  # the angled tip: the edge sweeps up to the back
        edge_hw = hw * (1 - kiss ** 1.6)
        back_hw = hw * (1 - 0.15 * kiss)
        off = X - spine
        side = np.where(off < 0, -off - edge_hw, off - back_hw)
        d = np.maximum(side, 0)
        d = np.where(t < 0, np.hypot(np.maximum(np.abs(X) - hw0, 0), -Y), d)        # below the collar
        tip_x = curve + hw0 * 0.55
        d = np.where(t > 1, np.hypot(X - tip_x * 0.6 - spine * 0.4, (t - 1) * length), d)
        glow = np.clip(1 - d / pad, 0, 1) ** 2.2
        heat = 0.25 + 0.75 * tc ** 1.3 if lvl == 3 else 0.55 + 0.45 * tc            # hotter at the tip
        heat = heat * (t > -0.02)                                                     # nothing on the hilt
        # a hot line running along the cutting edge
        edge_line = np.exp(-((off + edge_hw) / 1.6) ** 2) * (tc > 0.03) * (t <= 1.0)
        col = np.array(AURA[lvl], np.float32)
        white = np.array((255, 225, 180) if lvl < 5 else (215, 240, 255), np.float32)
        strength = {3: 0.75, 4: 0.85, 5: 0.9}[lvl]
        rgb = (glow * heat)[..., None] * col * strength + (edge_line * heat * 0.6)[..., None] * white
        s = _cache[key] = _to_surface(rgb * (level / LEVELS))
    return s


def spine_point(base, tip, t):
    """A point on the katana's curved spine at fraction t (0 collar .. 1 tip)."""
    bx, by = base
    dx, dy = tip[0] - bx, tip[1] - by
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux                           # towards the blade's back (its curve)
    bend = KAT.CURVE * length * t * t
    return bx + dx * t + nx * bend, by + dy * t + ny * bend


def prewarm():
    """Build the sprites up front so the first time you hit x3/x4/x5 doesn't stutter."""
    for pal in ("fire", "blue"):
        for size_i in range(4):
            for stage in range(STAGES):
                for level in range(1, LEVELS + 1):
                    flame_sprite(pal, size_i, stage, level)


# ---------- the effect ------------------------------------------------------------------
class BladeFire:
    def __init__(self):
        self.level = 1
        self.power = 0.0          # 0..1 eased intensity of the current effect
        self.shown_level = 1      # the look being shown (keeps showing while it fades out)
        self.flames = []          # [x, y, vx, vy, life, max_life, size_i, pal]
        self.sparks = []          # [x, y, vx, vy, life, max_life, col]
        self.spawn_acc = 0.0
        self.spark_acc = 0.0
        self.last = None
        self.layer = None
        if pygame.display.get_surface() is not None:     # make it now, not mid-game at x3
            self.layer = pygame.Surface((C.W, C.H)).convert()
            prewarm()

    # kept for the debug overlay / tests
    @property
    def parts(self):
        return self.flames + self.sparks

    def prewarm_aura(self, length):
        """Build every brightness step of the curved glow for this blade, at load time."""
        if pygame.display.get_surface() is None:
            return
        for lvl in (3, 4, 5):
            for level in range(1, LEVELS + 1):
                aura_sprite(lvl, round(length / 4) * 4, level)

    def set_level(self, level):
        self.level = level
        if level >= 3:
            self.shown_level = level

    def update_and_draw(self, surf, base, tip, now, visible=True, full_length=None):
        dt = 0.0 if self.last is None else min(0.05, now - self.last)
        self.last = now
        target = 1.0 if self.level >= 3 and visible else 0.0
        self.power += (target - self.power) * min(1.0, dt * (5.0 if target else 3.0))
        if self.power < 0.02 and not self.flames and not self.sparks:
            self.power = 0.0
            return
        lvl = min(5, max(3, self.shown_level))
        pw = self.power
        bx, by = base
        tx, ty = tip
        pal = "blue" if lvl >= 5 else "fire"

        # ---- spawn ----
        if visible and pw > 0.05:
            self.spawn_acc += SPAWN[lvl] * dt * pw
            while self.spawn_acc >= 1.0:
                self.spawn_acc -= 1.0
                t = random.uniform(0.12, 1.0)
                x, y = spine_point(base, tip, t)
                x += random.uniform(-2, 2)
                size_i = min(3, int(t * 3.2 + random.random() * 0.8) + (1 if lvl >= 5 else 0))
                life = random.uniform(0.16, 0.3)       # short-lived: they cling to the blade
                self.flames.append([x, y, random.uniform(-12, 12), random.uniform(-110, -55),
                                    life, life, size_i, pal])
            self.spark_acc += SPARKS[lvl] * dt * pw
            while self.spark_acc >= 1.0:
                self.spark_acc -= 1.0
                t = random.uniform(0.4, 1.0)
                x, y = spine_point(base, tip, t)
                a = random.uniform(-math.pi * 0.85, -math.pi * 0.15)      # mostly upwards
                sp = random.uniform(120, 260)
                life = random.uniform(0.3, 0.6)
                col = (190, 235, 255) if lvl >= 5 else (255, 200, 110)
                self.sparks.append([x, y, math.cos(a) * sp, math.sin(a) * sp, life, life, col])

        # ---- move ----
        for p in self.flames:
            p[4] -= dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 1 - 2.5 * dt                       # sideways drift settles
            p[3] -= 160 * dt                           # hot air rises faster
        self.flames = [p for p in self.flames if p[4] > 0][-250:]
        for p in self.sparks:
            p[4] -= dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 220 * dt                           # sparks arc back down
        self.sparks = [p for p in self.sparks if p[4] > 0][-80:]

        # ---- the area we draw into: blade + particles, padded ----
        xs = [bx, tx] + [p[0] for p in self.flames] + [p[0] for p in self.sparks]
        ys = [by, ty] + [p[1] for p in self.flames] + [p[1] for p in self.sparks]
        pad = 50
        box = pygame.Rect(int(min(xs)) - pad, int(min(ys)) - pad,
                          int(max(xs) - min(xs)) + 2 * pad, int(max(ys) - min(ys)) + 2 * pad)
        box = box.clip(surf.get_rect())
        if box.w <= 0 or box.h <= 0:
            return
        if self.layer is None:
            self.layer = pygame.Surface((C.W, C.H)).convert()
        L = self.layer
        L.fill((0, 0, 0), box)
        add = pygame.BLEND_ADD

        # ---- heat aura along the blade ----
        if visible:
            length = math.hypot(tx - bx, ty - by)
            if length > 4:
                flick = 0.9 + 0.1 * math.sin(now * 19) * math.sin(now * 7.3)
                level = max(1, min(LEVELS, round(LEVELS * pw * flick)))
                # always the full blade's glow (one cached image), even while it's being drawn
                spr = aura_sprite(lvl, round((full_length or length) / 4) * 4, level)
                ang = math.atan2(ty - by, tx - bx)
                rot = pygame.transform.rotozoom(spr, KAT.angle_to_rotozoom(ang), 1.0)
                L.blit(rot, rot.get_rect(center=(round(bx), round(by))), special_flags=add)

        # ---- flames: soft teardrops, colour and brightness by age ----
        for p in self.flames:
            u = p[4] / p[5]                            # 1 young .. 0 old
            stage = min(STAGES - 1, int((1 - u) * STAGES))
            level = max(1, min(LEVELS, round(LEVELS * pw * min(1.0, u * 2.6))))
            spr = flame_sprite(p[7], p[6], stage, level)
            w, h = spr.get_size()
            L.blit(spr, (p[0] - w / 2, p[1] - h * 0.62), special_flags=add)

        # ---- sparks: a bright head with a short streak behind ----
        for p in self.sparks:
            u = p[4] / p[5]
            k = pw * u
            col = p[6]
            tail = (p[0] - p[2] * 0.03, p[1] - p[3] * 0.03)
            pygame.draw.line(L, tuple(int(c * k) for c in col), tail, (p[0], p[1]), 2)
            spr = dot_sprite(col, 4, max(1, min(LEVELS, round(LEVELS * k))))
            L.blit(spr, (p[0] - 4, p[1] - 4), special_flags=add)

        # ---- x5: a fine arc of electricity now and then ----
        if visible and lvl >= 5 and random.random() < 0.18 * pw:
            t = random.uniform(0.25, 1.0)
            x, y = spine_point(base, tip, t)
            a = random.uniform(0, 2 * math.pi)
            pts = [(x, y)]
            for _ in range(5):
                a += random.uniform(-0.7, 0.7)
                x += math.cos(a) * random.uniform(5, 9)
                y += math.sin(a) * random.uniform(5, 9)
                pts.append((x, y))
            pygame.draw.lines(L, (60, 120, 200), False, pts, 3)     # soft outer
            pygame.draw.lines(L, (200, 240, 255), False, pts, 1)    # bright core

        surf.blit(L, box, area=box, special_flags=add)

    def trail_color(self, steel):
        """The swoosh behind the blade takes on the fire colour."""
        if self.power <= 0:
            return steel
        col = TRAIL.get(min(5, max(3, self.shown_level)), steel)
        return tuple(int(s + (c - s) * self.power) for s, c in zip(steel, col))
