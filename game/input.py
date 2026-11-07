"""Input sources. Each gives the game one SwordSample per frame."""
import math
import time
from dataclasses import dataclass

import pygame

MOUSE_TURN_SPEED = 4.0    # rad/s for Q / E


@dataclass
class SwordSample:
    active: bool          # sword drawn (fist / mouse button)
    visible: bool         # hand seen at all
    base: tuple           # canvas pixels
    angle: float          # radians, 0 = pointing right, positive = clockwise on screen
    t: float              # time.monotonic() of this sample
    new: bool             # True if this is a fresh sample (vision may be slower than 60 fps)


class MouseInput:
    """Left button held = sword drawn. The katana stands upright and leans with your swing; Q/E tilt."""
    name = "mouse"
    LEAN = 0.9          # max lean in radians
    LEAN_SPEED = 1400   # px/s of sideways speed for most of the lean

    def __init__(self):
        self.pos = pygame.mouse.get_pos()
        self.down = False
        self.tilt = 0.0                 # extra angle from Q / E
        self.angle = -math.pi / 2       # pointing up
        self.vx = 0.0                   # smoothed sideways speed
        self.last_pos, self.last_t = self.pos, time.monotonic()

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.pos = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.down, self.pos = True, event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.down = False

    def update(self, dt):
        now = time.monotonic()
        gap = max(1e-4, now - self.last_t)
        raw_vx = (self.pos[0] - self.last_pos[0]) / gap
        self.vx += (raw_vx - self.vx) * min(1.0, 18 * dt)        # smooth out uneven mouse events
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            self.tilt -= MOUSE_TURN_SPEED * dt
        if keys[pygame.K_e]:
            self.tilt += MOUSE_TURN_SPEED * dt
        # the tip trails behind the swing like it has weight; never flips
        target = -math.pi / 2 - self.LEAN * math.tanh(self.vx / self.LEAN_SPEED) + self.tilt
        self.angle += (target - self.angle) * min(1.0, 14 * dt)
        self.last_pos, self.last_t = self.pos, now
        return SwordSample(self.down, True, self.pos, self.angle, now, True)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class HandInput:
    """Reads get_hand_state() from vision. Never blocks; copes with slow or missing frames."""
    name = "hand"
    STALE = 0.25          # a HandState older than this counts as "hand not seen"

    def __init__(self):
        self.last_t = None
        self.lost_since = None
        self.pause_pose = False
        self.state = None

    def update(self, dt):
        from game import bridge, config
        now = time.monotonic()
        hs = bridge.get_hand_state()
        self.state = hs
        if hs is None:
            visible, active, base, angle, t, new = False, False, (0, 0), -math.pi / 2, now, False
            self.pause_pose = False
        else:
            fresh = now - hs.t < self.STALE
            visible = bool(hs.sword_visible) and fresh
            active = visible and bool(hs.sword_active)
            bx, by = hs.blade_base
            base = (bx * config.WIDTH, by * config.HEIGHT)
            angle, t = hs.blade_angle, hs.t
            new = hs.t != self.last_t
            self.last_t = hs.t
            self.pause_pose = bool(hs.pause_pose) and fresh
        if visible:
            self.lost_since = None
        elif self.lost_since is None:
            self.lost_since = now
        return SwordSample(active, visible, base, angle, t, new)

    @property
    def lost_for(self):
        return 0.0 if self.lost_since is None else time.monotonic() - self.lost_since

    @property
    def age(self):
        return None if self.state is None else time.monotonic() - self.state.t


def make_input(mode):
    return HandInput() if mode == "hand" else MouseInput()
