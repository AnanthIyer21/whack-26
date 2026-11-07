"""Turns noisy per-frame readings into steady states the game can trust.

GripStabiliser:   grip score -> GRIP / OPEN / UNCLEAR with hysteresis.
HandCounter:      which hand is the sword hand, debounced hands_in_frame,
                  and a short grace period when the hand vanishes mid-swing.
BladeSmoother:    One Euro on blade base and angle, with the side-on hold.
"""
import math

import numpy as np

from vision import config
from vision.geometry import raw_grip
from vision.one_euro import AngleFilter, OneEuroFilter, lerp_angle

GRIP, OPEN, UNCLEAR = "GRIP", "OPEN", "UNCLEAR"


class GripStabiliser:
    """Enter GRIP fast (2 frames), leave slowly (3 frames below a lower threshold)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = UNCLEAR
        self._enter = 0
        self._exit = 0

    def update(self, score, n_curled):
        if self.state == GRIP:
            self._exit = self._exit + 1 if score <= config.GRIP_EXIT else 0
            if self._exit >= config.GRIP_EXIT_FRAMES:
                self._exit = 0
                self.state = OPEN if score <= config.OPEN_BELOW else UNCLEAR
        else:
            self._enter = self._enter + 1 if raw_grip(score, n_curled) else 0
            if self._enter >= config.GRIP_ENTER_FRAMES:
                self._enter = 0
                self._exit = 0
                self.state = GRIP
            else:
                self.state = OPEN if score <= config.OPEN_BELOW else UNCLEAR
        return self.state


class HandCounter:
    """Picks the sword hand and debounces the hand count.

    update() returns (sword_hand or None, hands_in_frame, held) where held=True
    means "no detection this frame but we're inside the grace period: reuse the
    last state". When the grace runs out it returns (None, 0, False) and sets
    `lost` so the caller can reset its filters.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.last_hand = None
        self.last_seen_t = None
        self.count = 0          # reported hands_in_frame
        self._two_run = 0       # frames in a row with 2 hands seen
        self._one_run = 0       # frames in a row with 1 hand seen (while reporting 2)
        self.lost = False

    def update(self, hands, t):
        self.lost = False
        if not hands:
            if self.last_hand is not None and t - self.last_seen_t <= config.LOST_GRACE_S:
                return self.last_hand, self.count, True
            if self.last_hand is not None:
                self.lost = True
            self.last_hand, self.last_seen_t, self.count = None, None, 0
            self._two_run = self._one_run = 0
            return None, 0, False

        # Sword hand: the one nearest to where the sword hand just was.
        if self.last_hand is not None and len(hands) > 1:
            prev = self.last_hand.img[0, :2]
            sword = min(hands, key=lambda h: np.linalg.norm(h.img[0, :2] - prev))
        else:
            sword = max(hands, key=lambda h: h.score)

        # Debounced count: switch 1 <-> 2 only after TWO_HANDS_FRAMES in a row.
        if len(hands) >= 2:
            self._two_run += 1
            self._one_run = 0
        else:
            self._one_run += 1
            self._two_run = 0
        if self.count == 2:
            if self._one_run >= config.TWO_HANDS_FRAMES:
                self.count = 1
        elif self._two_run >= config.TWO_HANDS_FRAMES:
            self.count = 2
        else:
            self.count = 1

        self.last_hand, self.last_seen_t = sword, t
        return sword, self.count, False


class BladeSmoother:
    def __init__(self):
        self.pos = OneEuroFilter(config.POS_MIN_CUTOFF, config.POS_BETA, config.POS_D_CUTOFF)
        self.ang = AngleFilter(config.ANG_MIN_CUTOFF, config.ANG_BETA, config.ANG_D_CUTOFF)
        self.reset()

    def reset(self):
        self.pos.reset()
        self.ang.reset()
        self.angle = None            # last smoothed output
        self.held = None             # angle held while side-on
        self._recover_t = None       # when we came back from side-on
        self.side_on = False

    def update(self, base_xy, raw_angle, foreshorten, t):
        base = self.pos(base_xy, t)
        target = raw_angle
        if foreshorten < config.SIDE_ON_RATIO and self.angle is not None:
            # Fist pointing at the camera: the 2D angle is noise. Hold the last good one.
            if self.held is None:
                self.held = self.angle
            self.side_on = True
            self._recover_t = None
            target = self.held
        elif self.held is not None:
            # Reliable again: blend from the held angle back to the live one.
            self.side_on = False
            if self._recover_t is None:
                self._recover_t = t
            w = min(1.0, (t - self._recover_t) / config.SIDE_ON_BLEND_S)
            target = lerp_angle(self.held, raw_angle, w)
            if w >= 1.0:
                self.held = None
                self._recover_t = None
        self.angle = self.ang(target, t)
        return (float(base[0]), float(base[1])), self.angle

    def coast(self, t):
        """No detection this frame (inside the grace period): keep the blade moving
        along its last smoothed velocity, slowing down, so a fast swing still cuts.

        Moves the position filter's own state too, so when the hand is found again
        the smoothing carries on from here instead of snapping back.
        """
        f = self.pos
        if f._x is None or f._t is None:
            return None
        dt = t - f._t
        if dt <= 0:
            return (float(f._x[0]), float(f._x[1])), self.angle
        f._dx = f._dx * math.exp(-config.COAST_DAMPING * dt)
        f._x = np.clip(f._x + f._dx * dt, 0.0, 1.0)
        f._t = t
        return (float(f._x[0]), float(f._x[1])), self.angle
