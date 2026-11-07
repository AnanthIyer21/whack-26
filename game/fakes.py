"""Stand-ins for teammates' code, used only when shared/ doesn't exist yet.

Follows SPEC.md on main exactly. This is NOT real vision (that's Aaron's) and NOT
the real rival (that's Ananth's) - it only lets the game run and be tested alone.
"""
import queue
import threading
import time
from dataclasses import dataclass, replace

BLADE_LENGTH = 0.30  # fraction of screen height


@dataclass
class HandState:
    sword_hand: str = "right"
    sword_visible: bool = False
    sword_active: bool = False
    blade_base: tuple = (0.5, 0.5)
    blade_angle: float = 0.0
    pause_pose: bool = False
    gesture: str = "none"
    t: float = 0.0


_lock = threading.Lock()
_state = HandState(t=time.monotonic())

events = queue.Queue()
rival_lines = queue.Queue()


def get_hand_state():
    with _lock:
        return replace(_state)  # a copy, so the game never sees a half-written state


def set_hand_state(**fields):
    """Used by fake vision scripts and tests to publish a new HandState."""
    global _state
    with _lock:
        _state = replace(_state, t=time.monotonic(), **fields)


def set_sword_hand(hand):
    set_hand_state(sword_hand=hand)
    print(f"[fake vision] sword hand set to {hand}")


def get_latest_frame():
    return None  # no camera in the fake


_FAKE_LINES = {
    "game_start": ("Oh good, another victim.", "smug"),
    "bomb_hit": ("HA! You hit the bomb!", "gloating"),
    "streak": ("Okay... lucky streak. It won't last.", "rattled"),
    "combo": ("A combo? Who's helping you?", "rattled"),
    "miss": ("Missed one. Shocking.", "smug"),
}


def start_fake_rival(events_q, lines_q):
    """Prints every event and answers some with canned lines (standalone testing only)."""
    def loop():
        while True:
            ev = events_q.get()
            print(f"[fake rival] {ev}")
            if ev["type"] == "game_over":
                time.sleep(1.5)  # pretend Claude is thinking
                lines_q.put({"text": f"{ev['score']} points? I've seen better from a blender.",
                             "mood": "gloating", "duration": 4.0,
                             "kind": "final_roast", "round_id": ev.get("round_id")})
            elif ev["type"] in _FAKE_LINES:
                text, mood = _FAKE_LINES[ev["type"]]
                lines_q.put({"text": text, "mood": mood, "duration": 2.5})

    threading.Thread(target=loop, name="fake-rival", daemon=True).start()
