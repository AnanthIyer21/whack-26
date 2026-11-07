"""Fake vision: a moving blade plus a scripted grip/open/two-hands/no-hand cycle.

Publishes HandState at ~30 Hz and a synthetic RGB "camera" frame, so the game's
preview and auto-pause paths can be built before the real vision lands.
"""

import math
import time

import numpy as np

import shared

# (seconds, sword_active, hands_in_frame, label)
CYCLE = (
    (8.0, True, 1, "gripping"),
    (2.0, False, 1, "open hand"),
    (2.0, True, 2, "two hands"),
    (2.0, False, 0, "no hand"),
)
HZ = 30
FRAME_W = 640
FRAME_H = 360


def _phase(elapsed):
    total = 0.0
    for step in CYCLE:
        total += step[0]
    t = elapsed % total
    for step in CYCLE:
        if t < step[0]:
            return step
        t -= step[0]
    return CYCLE[0]


def _fake_frame(elapsed):
    """A slowly shifting colour gradient, so you can see the preview is live."""
    shift = int(elapsed * 40) % 256
    xs = np.linspace(0, 255, FRAME_W, dtype=np.uint16)
    row = ((xs + shift) % 256).astype(np.uint8)
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    frame[:, :, 0] = row
    frame[:, :, 1] = 60
    frame[:, :, 2] = 255 - row
    return frame


def run(stop_event):
    start = time.monotonic()
    period = 1.0 / HZ
    while not stop_event.is_set():
        now = time.monotonic()
        elapsed = now - start
        duration, active, hands, label = _phase(elapsed)

        # Figure-of-eight path for the fist, blade swinging back and forth.
        x = 0.5 + 0.3 * math.sin(elapsed * 1.3)
        y = 0.55 + 0.2 * math.sin(elapsed * 2.6)
        angle = shared.BLADE_UP + 0.9 * math.sin(elapsed * 2.0)

        state = shared.HandState(
            sword_visible=hands >= 1,
            sword_active=active and hands == 1,
            blade_base=(x, y),
            blade_angle=angle,
            hands_in_frame=hands,
            gesture="none",
            confidence=0.9 if hands >= 1 else 0.0,
            t=now,
        )
        shared.set_hand_state(state)
        shared.set_latest_frame(_fake_frame(elapsed), now)
        stop_event.wait(period)
