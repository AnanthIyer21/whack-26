"""Stand-ins for Ananth's shared/ until it lands on staging.

Same HandState fields as SPEC.md, and the same get/set shape. When shared/
lands, vision/adapter code swaps these for the real ones; nothing else changes.
"""
import threading
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HandState:
    sword_visible: bool = False
    sword_active: bool = False
    blade_base: tuple = (0.5, 0.5)
    blade_angle: float = -1.5707963267948966   # pointing up
    hands_in_frame: int = 0
    gesture: str = "none"
    confidence: float = 0.0
    t: float = field(default_factory=time.monotonic)


class FakeShared:
    """Thread-safe latest-value slots: one writer (vision), many readers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = HandState()
        self._frame = None

    def set_hand_state(self, **fields):
        s = HandState(**fields)
        with self._lock:
            self._state = s

    def get_hand_state(self):
        with self._lock:
            return self._state

    def set_latest_frame(self, frame):
        with self._lock:
            self._frame = frame

    def get_latest_frame(self):
        with self._lock:
            return self._frame
