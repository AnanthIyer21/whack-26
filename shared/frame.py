"""Latest camera frame: vision -> anyone (for the webcam preview).

Only vision ever opens the camera. get_latest_frame() returns (frame, t):
frame is an RGB NumPy array (H, W, 3), already mirrored like a selfie so it
lines up with HandState.blade_base, and marked read-only. t is the
time.monotonic() of the capture. Before the first frame: (None, 0.0).
"""

import threading

_lock = threading.Lock()
_frame = None
_t = 0.0


def set_latest_frame(frame, t):
    """Vision only. Pass a fresh array each time; it is made read-only here."""
    global _frame, _t
    if frame is not None:
        frame.flags.writeable = False
    with _lock:
        _frame = frame
        _t = t


def get_latest_frame():
    with _lock:
        return _frame, _t
