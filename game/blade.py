"""The sword: draw animation, swept-area hit shapes, tip speed and the glowing ribbon trail.

States
  sheathed - no blade (title, pause, before the run)
  drawing  - growing out of the fist over DRAW_TIME; can't cut yet
  drawn    - full blade, can cut once it has two fresh, close-together samples
  frozen   - hand went bad: blade stays at its last position, grey, can't cut
"""
import math
from dataclasses import dataclass

import pygame

from . import config as C
from .geometry import wrap_angle
from .blade_fx import BladeFire
from .katana import angle_to_rotozoom, make_katana


@dataclass
class Sweep:
    quad: list          # 4 points: old base, old tip, new tip, new base
    speed: float        # tip speed, screen heights per second
    direction: tuple    # unit vector of tip motion (juice sprays this way)
    angle: float        # blade angle at this substep (the cut line follows the blade)
    bridged: bool = False   # a "lag sweep": bridged across a tracking gap, or a predicted/
                            # gliding estimate. The game is more forgiving with these.
    t: float = 0.0          # when the blade was (probably) here: lag cuts check fruit positions
                            # at this moment, not where the fruit has moved to since


def _lerp(a, b, u):
    return a + (b - a) * u


class Blade:
    def __init__(self, length_frac):
        self.length = length_frac * C.H
        self._sprite = make_katana(self.length)
        self._sprite_frozen = make_katana(self.length, frozen=True)
        if pygame.display.get_surface() is not None:   # fast blits once there's a window
            self._sprite = self._sprite.convert_alpha()
            self._sprite_frozen = self._sprite_frozen.convert_alpha()
        self.state = "sheathed"
        self.base = (C.W / 2, C.H / 2)
        self.angle = C.MOUSE_START_ANGLE
        self.draw_t0 = 0.0
        self.speed = 0.0           # latest tip speed (screen heights / s), for debug + effects
        self.fire = BladeFire()     # streak fire (x3 heated, x4 on fire, x5 blue inferno)
        self._hist = []            # recent fresh samples: (t, base, angle, when)
        self._swing_speed = 0.0    # speed of the last normal (un-lagged) segment
        self.bridges = 0           # how many lag gaps we've bridged (debug overlay)
        self._last_t = None
        self._pending = []         # Sweeps not yet consumed by the game
        self._trail = []           # (t, base, tip) for the ribbon

    # ---- state changes -------------------------------------------------------------
    def reset_history(self):
        """Forget past positions so a jump (pause/resume, draw, input switch) can't cut."""
        self._hist.clear()
        self._pending.clear()
        self._trail.clear()
        self._last_t = None
        self.speed = 0.0
        self._swing_speed = 0.0

    def draw_out(self, now):
        self.state = "drawing"
        self.draw_t0 = now
        self.reset_history()

    def sheathe(self):
        self.state = "sheathed"
        self.reset_history()

    def freeze(self):
        """Hand went bad (lost, opened, two hands). Keep the last good sample as an anchor:
        if tracking comes back within MAX_BRIDGE_GAP, the path from there gets swept."""
        if self.state in ("drawing", "drawn"):
            self.state = "frozen"
            self._hist = self._hist[-1:]
            self._pending.clear()
            self._trail.clear()
            self.speed = 0.0

    def unfreeze(self):
        if self.state == "frozen":
            self.state = "drawn"
            self._last_t = None        # the next sample is new, and bridges from the anchor

    @property
    def visible(self):
        return self.state != "sheathed"

    @property
    def armed(self):
        return self.state == "drawn"

    def grow(self, now):
        if self.state != "drawing":
            return 1.0
        return min(1.0, (now - self.draw_t0) / C.DRAW_TIME)

    def tip(self, now=None, base=None, angle=None):
        base = self.base if base is None else base
        angle = self.angle if angle is None else angle
        L = self.length * (self.grow(now) if now is not None else 1.0)
        return (base[0] + math.cos(angle) * L, base[1] + math.sin(angle) * L)

    # ---- per-frame update ----------------------------------------------------------
    def update(self, sample, now):
        """Feed the latest input sample. Only call while the hand state is good."""
        if self.state == "drawing" and self.grow(now) >= 1.0:
            self.state = "drawn"
        if self.state == "frozen" or self.state == "sheathed":
            return
        if sample.t == self._last_t:
            return  # same vision frame as last time: nothing new (vision ~30 fps, game 60)
        self._last_t = sample.t
        self.base, self.angle = sample.base, sample.angle
        was_predicted, self._last_predicted = getattr(self, "_last_predicted", False), sample.predicted

        self._trail.append((now, self.base, self.tip(now)))
        self._hist.append((sample.t, self.base, self.angle, sample.when if sample.when is not None else sample.t))
        if len(self._hist) > 2:
            self._hist.pop(0)
        if len(self._hist) < 2:
            self.speed = 0.0
            return

        (t0, b0, a0, w0), (t1, b1, a1, w1) = self._hist
        gap = t1 - t0
        jump = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
        bridged = gap > C.MAX_SAMPLE_GAP
        lag = bridged or sample.predicted or was_predicted
        if gap <= 0 or gap > C.MAX_BRIDGE_GAP or (bridged and jump > C.MAX_BRIDGE_DIST * C.W):
            # Too long (or a tracking glitch that jumped across the screen): fresh start, no slash.
            self._hist = [self._hist[-1]]
            self.speed = 0.0
            self._swing_speed = 0.0
            return

        tip0 = self.tip(base=b0, angle=a0)
        tip1 = self.tip(base=b1, angle=a1)
        dx, dy = tip1[0] - tip0[0], tip1[1] - tip0[1]
        dist = math.hypot(dx, dy)
        self.speed = dist / gap / C.H
        if bridged:
            # Tracking lagged mid-swing. Averaged over the gap the swing looks slow, so also
            # trust the speed you were swinging at going into the lag.
            self.speed = max(self.speed, self._swing_speed)
            self.bridges += 1
            self._trail.insert(len(self._trail) - 1, (now, b0, tip0))   # show the bridged swoosh
        else:
            self._swing_speed = self.speed
        direction = (dx / dist, dy / dist) if dist > 1e-6 else (1.0, 0.0)

        if self.state != "drawn":
            return  # still growing: no cuts yet
        # Split big rotations into substeps so the swept area is never a bowtie
        # and never misses the arc's bulge.
        da = wrap_angle(a1 - a0)
        n = max(1, math.ceil(abs(da) / C.MAX_SUBSTEP_ANGLE))
        if lag:                           # long guessed paths: small steps, each with its own time
            n = max(n, math.ceil(max(jump, dist) / C.LAG_SUBSTEP_PX))
        prev_b, prev_a = b0, a0
        for i in range(1, n + 1):
            u = i / n
            nb = (_lerp(b0[0], b1[0], u), _lerp(b0[1], b1[1], u))
            na = a0 + da * u
            quad = [prev_b, self.tip(base=prev_b, angle=prev_a),
                    self.tip(base=nb, angle=na), nb]
            ts = w0 + (w1 - w0) * (i - 0.5) / n      # when the blade (probably) passed here
            self._pending.append(Sweep(quad, self.speed, direction, na, lag, ts))
            prev_b, prev_a = nb, na

    def take_sweeps(self):
        """Swept shapes since the last call (the game tests fruit against them)."""
        out, self._pending = self._pending, []
        return out

    # ---- drawing -------------------------------------------------------------------
    def draw(self, surf, glow_layer, now):
        # Trail: swept ribbon over the last TRAIL_TIME, fading with age, brighter when fast.
        self._trail = [p for p in self._trail if now - p[0] <= C.TRAIL_TIME]
        trail_box = None
        if self.state in ("drawn", "drawing") and len(self._trail) >= 2:
            pts = [p for _, b, t in self._trail for p in (b, t)]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            trail_box = pygame.Rect(min(xs) - 4, min(ys) - 4, max(xs) - min(xs) + 8, max(ys) - min(ys) + 8)
            trail_box = trail_box.clip(glow_layer.get_rect())
            bright = max(0.25, min(1.0, self.speed / (C.CUT_SPEED * 1.5)))
            col = self.fire.trail_color(C.GLOW)
            for (ta, ba, pa), (tb, bb, pb) in zip(self._trail, self._trail[1:]):
                age = (now - ta) / C.TRAIL_TIME
                a = int(105 * (1 - age) ** 1.5 * bright)
                if a > 0:
                    pygame.draw.polygon(glow_layer, (*col, a), [ba, pa, pb, bb])
            # bright leading edge along the tip path
            tips = [p for _, _, p in self._trail]
            pygame.draw.lines(glow_layer, (255, 255, 255, int(200 * bright)), False, tips, 3)

        # the trail goes BEHIND the katana: copy just the box around it, then clear that box
        if trail_box is not None:
            surf.blit(glow_layer, trail_box, area=trail_box)
            glow_layer.fill((0, 0, 0, 0), trail_box)
        if not self.visible:
            self.fire.update_and_draw(surf, self.base, self.tip(), now, visible=False)  # let embers die out
            return

        g = self.grow(now)
        frozen = self.state == "frozen"
        img = self._sprite_frozen if frozen else self._sprite
        if g < 1.0:                       # sliding out of the fist: hide the part not drawn yet
            img = img.copy()
            pivot_y = img.get_height() / 2
            img.fill((0, 0, 0, 0), pygame.Rect(0, 0, img.get_width(), int(pivot_y - self.length * g)))
        rot = pygame.transform.rotozoom(img, angle_to_rotozoom(self.angle), 1.0)
        surf.blit(rot, rot.get_rect(center=(int(self.base[0]), int(self.base[1]))))
        self.fire.update_and_draw(surf, self.base, self.tip(now), now, visible=not frozen)

        # glint at the tip right as the draw finishes ("shing")
        since = now - self.draw_t0 - C.DRAW_TIME
        if 0 <= since < 0.15 and self.state in ("drawing", "drawn"):
            tx, ty = self.tip()
            r = 6 + 40 * since
            a = int(230 * (1 - since / 0.15))
            pygame.draw.circle(glow_layer, (255, 255, 255, a), (tx, ty), r * 0.5)
            pygame.draw.line(glow_layer, (255, 255, 255, a), (tx - r * 1.6, ty), (tx + r * 1.6, ty), 2)
            pygame.draw.line(glow_layer, (255, 255, 255, a), (tx, ty - r * 1.6), (tx, ty + r * 1.6), 2)


def _mix(c1, c2, u):
    u = max(0.0, min(1.0, u))
    return tuple(int(a + (b - a) * u) for a, b in zip(c1, c2))
