"""Swing prediction: keeps the katana flying when hand tracking drops out mid-swing.

Fast swings blur your hand on camera and MediaPipe loses it for ~0.1-0.4 s. Vision then
holds the hand for 0.15 s (its "coast" barely moves the blade) and after that reports no
hand, so without this the katana sticks in place and then teleports.

While tracking is live we measure how fast the blade is moving and turning. If tracking
drops out while you're swinging, we keep the blade going along that path, slowing down
naturally, for up to PREDICT_MAX. It stays armed, so fruit in the path get cut. When the
hand is found again, the blade glides to it over GLIDE_TIME instead of jumping.

Vision's hold is spotted by its confidence repeating exactly frame after frame (a real
detection always changes it slightly); it's also treated as lost once vision says so.

Output sample times are ARRIVAL times (when the game got each new sample), so they always
increase, even when we switch between real and predicted samples.
"""
from collections import deque
from dataclasses import replace
import math

from . import config as C
from .geometry import wrap_angle


def _ease(u):
    return 1 - (1 - u) ** 3


class SwingPredictor:
    def __init__(self):
        self.reset()

    def reset(self):
        self.hist = deque(maxlen=8)     # live samples: (arrival time, base, angle)
        self.mode = "live"              # live | predict | hover | glide | lost
        self.out = None                 # last sample handed to the game
        self.last_raw_t = None
        self.pred = None                # (t0, base, angle, vx, vy, w)
        self.glide = None               # (t0, base, angle)
        self.anchor = None              # last good pose handed out: (time, base, angle)
        self.predictions = 0            # how many dropouts we've predicted through (debug)

    def velocity(self):
        """(vx, vy) px/s and angular speed rad/s over the last ~VEL_WINDOW of live samples."""
        if len(self.hist) < 2:
            return 0.0, 0.0, 0.0
        t1, b1, a1 = self.hist[-1]
        first = None
        for t, b, a in self.hist:
            if t1 - t <= C.PREDICT_VEL_WINDOW:
                first = (t, b, a)
                break
        if first is None or t1 - first[0] <= 1e-6:
            return 0.0, 0.0, 0.0
        t0, b0, a0 = first
        dt = t1 - t0
        return (b1[0] - b0[0]) / dt, (b1[1] - b0[1]) / dt, wrap_angle(a1 - a0) / dt

    def _swinging(self, vx, vy, w):
        return math.hypot(vx, vy) >= C.PREDICT_MIN_SPEED * C.H or abs(w) >= C.PREDICT_MIN_SPIN

    def process(self, raw, now):
        new = raw.t != self.last_raw_t
        if new:
            self.last_raw_t = raw.t
        live = raw.good and not raw.held

        if live:
            if new:
                if self.mode in ("predict", "hover", "lost"):
                    if self.mode == "lost":
                        self.hist.clear()     # don't measure speed across the dropout
                    self.mode = "live"
                    a = self.anchor
                    if a is not None and now - a[0] <= C.MAX_BRIDGE_GAP:
                        jump = math.hypot(raw.base[0] - a[1][0], raw.base[1] - a[1][1])
                        if jump > C.GLIDE_MIN_DIST:   # glide over instead of teleporting
                            self.glide = (now, a[1], a[2])
                            self.glide_from_t = a[0]
                            self.mode = "glide"
                self.hist.append((now, raw.base, raw.angle))
            if self.mode == "glide":
                t0, b0, a0 = self.glide
                u = (now - t0) / C.GLIDE_TIME
                if u < 1.0:
                    e = _ease(u)
                    base = (b0[0] + (raw.base[0] - b0[0]) * e, b0[1] + (raw.base[1] - b0[1]) * e)
                    angle = a0 + wrap_angle(raw.angle - a0) * e
                    # the hand really travelled this path during the whole dropout, not in
                    # these 80 ms: stamp each point with when it was (probably) there
                    when = self.glide_from_t + (t0 - self.glide_from_t) * e
                    self.out = replace(raw, base=base, angle=angle, t=now, held=False, predicted=True,
                                       when=when)
                    self.anchor = (now, base, angle)
                    return self.out
                self.mode = "live"
                self.out = replace(raw, t=now)
                self.anchor = (now, raw.base, raw.angle)
                return self.out
            if new or self.out is None or not self.out.good:
                self.out = replace(raw, t=now)
                self.anchor = (now, raw.base, raw.angle)
            return self.out

        # ---- not live ----
        # Only a LOST hand is predicted through (vision's hold, no hand seen, or stale data).
        # An open hand or two hands are real, deliberate states: pass them straight through.
        lost_hand = raw.held or raw.stale or raw.hands == 0
        if not lost_hand:
            if self.mode in ("predict", "hover"):
                self.mode = "lost"
            self.out = replace(raw, t=now)
            return self.out
        if self.mode in ("live", "glide") and self.hist:
            vx, vy, w = self.velocity()
            t_last, b_last, a_last = self.hist[-1]
            start = self.out if self.out is not None and self.out.good else None
            if self._swinging(vx, vy, w) and start is not None and now - t_last <= C.PREDICT_MAX:
                self.pred = (t_last, start.base, start.angle, vx, vy, w)
                self.mode = "predict"
                self.predictions += 1
            else:
                self.mode = "lost"

        if self.mode == "predict":
            t0, b0, a0, vx, vy, w = self.pred
            dt = now - t0
            if dt <= C.PREDICT_MAX:
                k = C.PREDICT_DAMPING
                f = (1 - math.exp(-k * dt)) / k          # distance factor: starts at v, slows down
                x = min(max(b0[0] + vx * f, 0.0), C.W)
                y = min(max(b0[1] + vy * f, 0.0), C.H)
                self.out = replace(raw, base=(x, y), angle=a0 + w * f, gripping=True, hands=1,
                                   stale=False, held=False, predicted=True, t=now)
                self.anchor = (now, self.out.base, self.out.angle)
                return self.out
            self.mode = "hover"

        if self.mode == "hover":
            # prediction used up: hover where it ended (still armed, not grey) until the
            # bridge window runs out, so a hand that comes back a little late glides on
            if now - self.pred[0] <= C.HOVER_MAX and self.out is not None:
                return self.out
            self.mode = "lost"

        # lost: if vision is still holding (reports good), hold the blade where it ended up;
        # otherwise pass the bad state through so the game greys the blade / pauses as usual
        if raw.good and self.out is not None:
            return self.out
        self.out = replace(raw, t=now)
        return self.out
