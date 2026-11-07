"""Input sources. Each gives the game one SwordSample per frame."""
import math
import time
from dataclasses import dataclass

import pygame

MOUSE_TURN_SPEED = 4.0    # rad/s for Q / E
MOUSE_MOVE_MIN = 150.0    # px/s before the blade follows your motion


@dataclass
class SwordSample:
    active: bool          # sword drawn (fist / mouse button)
    visible: bool         # hand seen at all
    base: tuple           # canvas pixels
    angle: float          # radians, 0 = pointing right, positive = clockwise on screen
    t: float              # time.monotonic() of this sample
    new: bool             # True if this is a fresh sample (vision may be slower than 60 fps)


class MouseInput:
    """Left button held = sword drawn. The blade swings broadside to your motion; Q/E tilt."""
    name = "mouse"

    def __init__(self):
        self.pos = pygame.mouse.get_pos()
        self.down = False
        self.angle = -math.pi / 2   # pointing up
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
        vx, vy = (self.pos[0] - self.last_pos[0]) / gap, (self.pos[1] - self.last_pos[1]) / gap
        if math.hypot(vx, vy) > MOUSE_MOVE_MIN:
            # point the blade at right angles to the motion, picking the side nearest "up"
            move = math.atan2(vy, vx)
            options = [move - math.pi / 2, move + math.pi / 2]
            target = min(options, key=lambda a: abs(_wrap(a + math.pi / 2)))
            self.angle += _wrap(target - self.angle) * min(1.0, 12 * dt)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            self.angle -= MOUSE_TURN_SPEED * dt
        if keys[pygame.K_e]:
            self.angle += MOUSE_TURN_SPEED * dt
        self.last_pos, self.last_t = self.pos, now
        return SwordSample(self.down, True, self.pos, self.angle, now, True)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def make_input(mode):
    if mode == "hand":
        print("[input] hand input arrives in step 3 - using the mouse for now")
    return MouseInput()
