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


def make_input(mode):
    if mode == "hand":
        print("[input] hand input arrives in step 3 - using the mouse for now")
    return MouseInput()
