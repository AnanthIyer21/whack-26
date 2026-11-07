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
    "pause": ("Taking a breather? Coward.", "smug"),
    "resume": ("Back for more humiliation?", "defensive"),
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


class FakeVision:
    """Pretend vision for testing HandInput without a camera, steered from the game window.

    The game feeds it the mouse and keys every frame; a thread publishes HandState at
    ~30 fps with a little jitter, like a real webcam pipeline would.
    Mouse = fist position, left button = fist closed, H = hide/show hand, O (hold) = palms up.
    """

    def __init__(self, width, height):
        self.W, self.H = width, height
        self.pos, self.down, self.visible, self.pose = (width / 2, height / 2), False, True, False
        self.angle, self.vx, self.last = -1.5708, 0.0, None
        threading.Thread(target=self._loop, name="fake-vision", daemon=True).start()

    def feed(self, pos, down, pose):
        self.pos, self.down, self.pose = pos, down, pose

    def toggle_visible(self):
        self.visible = not self.visible
        print(f"[fake vision] hand {'visible' if self.visible else 'HIDDEN'}")

    def _loop(self):
        import math
        import random
        while True:
            time.sleep(1 / 30)
            x, y = self.pos
            if self.last:
                self.vx += ((x - self.last[0]) * 30 - self.vx) * 0.5
            self.last = (x, y)
            self.angle = -math.pi / 2 - 0.9 * math.tanh(self.vx / 1400)
            jx, jy = random.uniform(-2, 2), random.uniform(-2, 2)
            set_hand_state(sword_visible=self.visible, sword_active=self.visible and self.down and not self.pose,
                           blade_base=((x + jx) / self.W, (y + jy) / self.H),
                           blade_angle=self.angle + random.uniform(-0.02, 0.02),
                           pause_pose=self.visible and self.pose)
