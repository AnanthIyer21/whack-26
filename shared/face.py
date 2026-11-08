"""FaceState: face thread (writer) -> rival (reader). Extension, only active with --face.

Same thread-safety idea as HandState: a frozen dataclass swapped whole under a
lock, so readers always see one consistent snapshot. Expressions only: nothing
here identifies a person, and no image is ever stored.
"""

import threading
from dataclasses import dataclass, field

EXPRESSIONS = ("smiling", "laughing", "shock", "frowning", "looking_away")


@dataclass(frozen=True)
class FaceState:
    face_visible: bool = False       # the player's face is readable this frame
    expression: str = "neutral"      # "neutral" or one of EXPRESSIONS (the one currently held)
    scores: dict = field(default_factory=dict)   # smoothed signals, e.g. {"smile": 0.12, "jaw": 0.05, ...}
    yaw: float = 0.0                 # degrees, relative to the player's usual head position
    pitch: float = 0.0               # degrees down, relative to the player's usual head position
    faces_in_view: int = 0
    calibrated: bool = False         # the 5 s warm-up is over
    t: float = 0.0                   # time.monotonic() of the frame this came from


_lock = threading.Lock()
_current = FaceState()


def set_face_state(state):
    global _current
    if not isinstance(state, FaceState):
        raise TypeError("set_face_state expects a FaceState")
    with _lock:
        _current = state


def get_face_state():
    with _lock:
        return _current
