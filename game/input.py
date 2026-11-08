"""Input sources. Both give the game the same thing each frame: a HandSample in screen pixels.

MouseInput  - mouse position = blade base, left button held = fist, the blade swings with
              momentum; keys 0/1/2 fake how many hands are in frame (to test the pause reasons).
HandInput   - reads get_hand_state() from vision. Never blocks.
"""
from dataclasses import dataclass
import math
import time

import pygame

from . import config as C
from .predict import SwingPredictor


@dataclass
class HandSample:
    base: tuple            # (x, y) blade base in screen pixels (logical 1280x720)
    angle: float           # radians, screen coords: 0 = right, -pi/2 = up
    gripping: bool         # sword_active
    hands: int             # hands_in_frame (0, 1, 2); stale vision -> 0
    t: float               # time of the sample (time.monotonic())
    stale: bool = False
    confidence: float = 1.0
    held: bool = False     # vision is holding a lost hand (not a real detection this frame)
    predicted: bool = False  # made up by the swing predictor (or gliding back): an estimate
    when: float = None     # estimated real time the hand was at this pose (glides after a
                           # dropout spread the path across the whole gap); None = same as t

    @property
    def good(self) -> bool:
        """Exactly one gripping hand: the only state you can play in."""
        return self.hands == 1 and self.gripping and not self.stale


class InputSource:
    name = "?"

    def handle_event(self, ev):  # keyboard / mouse events from pygame
        pass

    def poll(self, now: float) -> HandSample:
        raise NotImplementedError


class MouseInput(InputSource):
    """The mouse is the fist. The katana stays upright and leans into the way you move.

    Sideways speed sets a lean (up to MOUSE_MAX_TILT either side of upright), and the blade
    eases smoothly towards it: no pendulum, no wobble, no overshoot. It can never tip past
    sideways, so it is never upside down. When you stop, it glides back to upright.
    """
    name = "MOUSE"

    def __init__(self, length_px=None):
        self.fake_hands = 1
        self.last = None
        self.last_pos = None
        self.vx = 0.0
        self.angle = C.MOUSE_START_ANGLE

    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_0, pygame.K_1, pygame.K_2):
            self.fake_hands = ev.key - pygame.K_0

    def poll(self, now):
        x, y = pygame.mouse.get_pos()          # pygame.SCALED already maps to 1280x720
        held = pygame.mouse.get_pressed()[0]
        dt = 1 / 60 if self.last is None else min(max(now - self.last, 1e-3), C.MAX_DT)
        self.last = now
        if self.last_pos is None:
            base = (float(x), float(y))
        else:                                  # the katana follows the cursor with a little weight
            k = 1 - math.exp(-C.MOUSE_FOLLOW * dt)
            base = (self.last_pos[0] + (x - self.last_pos[0]) * k, self.last_pos[1] + (y - self.last_pos[1]) * k)
        if self.last_pos is not None:
            raw_vx = (base[0] - self.last_pos[0]) / dt
            k = 1 - math.exp(-dt / C.MOUSE_VEL_SMOOTH)        # smooth out jittery mouse deltas
            self.vx += (raw_vx - self.vx) * k
        self.last_pos = base

        lean = C.MOUSE_MAX_TILT * math.tanh(self.vx / C.MOUSE_TILT_SPEED)
        target = C.MOUSE_START_ANGLE + lean                   # -90 deg is straight up
        self.angle += (target - self.angle) * (1 - math.exp(-C.MOUSE_TILT_EASE * dt))
        return HandSample(base, self.angle, held, self.fake_hands, now)


class HandInput(InputSource):
    name = "HAND"

    def __init__(self, get_hand_state, viewport):
        self.get_hand_state = get_hand_state
        self.viewport = viewport               # maps normalised camera coords -> screen px
        self._last = None
        self._last_raw = None                  # (t, confidence, good) of the previous HandState
        self.predictor = SwingPredictor()

    def reset(self):
        self.predictor.reset()

    def poll(self, now):
        hs = None
        try:
            hs = self.get_hand_state()
        except Exception:
            hs = None
        if hs is None:
            base = self._last.base if self._last else (C.W / 2, C.H / 2)
            angle = self._last.angle if self._last else C.MOUSE_START_ANGLE
            return HandSample(base, angle, False, 0, now, stale=True)

        t = getattr(hs, "t", 0.0)
        stale = t <= 0 or (now - t) > C.HAND_STALE
        bx, by = hs.blade_base
        conf = float(getattr(hs, "confidence", 0.0))
        gripping = bool(hs.sword_active)
        # Vision's hold after losing the hand repeats the last confidence exactly; a real
        # detection always changes it a little.
        prev = self._last_raw
        held = (prev is not None and t != prev[0] and prev[2] and gripping and conf > 0
                and conf == prev[1])
        if prev is None or t != prev[0]:
            self._last_raw = (t, conf, gripping and not stale)
        sample = HandSample(
            base=self.viewport.norm_to_px(bx, by),
            angle=float(hs.blade_angle),
            gripping=gripping,
            hands=0 if stale else int(hs.hands_in_frame),
            t=t,
            stale=stale,
            confidence=conf,
            held=held,
        )
        self._last = sample
        return self.predictor.process(sample, now)


class Viewport:
    """Maps normalised camera coordinates (0..1, already selfie-mirrored) to screen pixels.

    The camera frame is cropped to fill 16:9 the same way for the background picture and for
    blade_base, so the sword lines up with the real fist. crop = (x0, y0, w, h) in 0..1 units.
    """

    def __init__(self):
        self.crop = (0.0, 0.0, 1.0, 1.0)

    def set_camera_size(self, cam_w, cam_h):
        target = C.W / C.H
        aspect = cam_w / cam_h
        if aspect > target:      # too wide: trim the sides
            w = target / aspect
            self.crop = ((1 - w) / 2, 0.0, w, 1.0)
        else:                    # too tall: trim top and bottom
            h = aspect / target
            self.crop = (0.0, (1 - h) / 2, 1.0, h)

    def norm_to_px(self, x, y):
        x0, y0, w, h = self.crop
        return ((x - x0) / w * C.W, (y - y0) / h * C.H)


def blade_tip(base, angle, length_px):
    return (base[0] + math.cos(angle) * length_px, base[1] + math.sin(angle) * length_px)
