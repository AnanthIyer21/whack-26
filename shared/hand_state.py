"""HandState: vision (writer) -> game (reader).

Thread safety: HandState is a frozen (immutable) dataclass. The vision thread
builds a brand new one each frame and swaps a single reference under a lock.
Readers get a complete, consistent snapshot and can never mutate it, so no
copying is needed and torn reads (base from one frame, angle from another) are
impossible.
"""

import threading
import time
from dataclasses import dataclass

from shared.constants import BLADE_UP


@dataclass(frozen=True)
class HandState:
    sword_visible: bool = False
    sword_active: bool = False          # the sword hand is gripping
    blade_base: tuple = (0.5, 0.5)      # (x, y) each 0..1; x mirrored like a selfie, y top to bottom
    blade_angle: float = BLADE_UP       # radians, smoothed (see constants.py for the convention)
    hands_in_frame: int = 0             # 0, 1 or 2
    gesture: str = "none"               # "none" until extensions
    confidence: float = 0.0             # 0..1
    t: float = 0.0                      # time.monotonic() of the camera frame


_lock = threading.Lock()
_current = HandState()


def set_hand_state(state):
    """Publish a new HandState (vision thread, or the game in mouse mode)."""
    global _current
    if not isinstance(state, HandState):
        raise TypeError("set_hand_state expects a HandState")
    with _lock:
        _current = state


def get_hand_state():
    """Latest HandState. Never blocks for longer than a reference swap."""
    with _lock:
        return _current


def mouse_hand_state(x, y, pressed, t=None):
    """Mouse sword: (x, y) normalised 0..1, holding the button means gripping.

    Releasing the button reads as 'not gripping', so it triggers the pause
    exactly like opening your fist would.
    """
    if t is None:
        t = time.monotonic()
    return HandState(
        sword_visible=True,
        sword_active=bool(pressed),
        blade_base=(x, y),
        blade_angle=BLADE_UP,
        hands_in_frame=1,
        gesture="none",
        confidence=1.0,
        t=t,
    )
