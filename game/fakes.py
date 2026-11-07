"""Stand-ins for shared/ until Ananth's version lands on staging.

Same names and shapes as the team spec, so swapping to the real thing is just an import.
Only used when shared/ is missing AND main.py didn't pass the real objects in.
"""
import queue
import threading
import time

BLADE_LENGTH = 0.30
DEFAULT_GAME_SECONDS = 60

events: "queue.Queue[dict]" = queue.Queue(maxsize=1000)
rival_lines: "queue.Queue[dict]" = queue.Queue(maxsize=100)


def get_hand_state():
    """No vision yet: there is never a hand."""
    return None


def get_latest_frame():
    """No vision yet: there is never a camera frame."""
    return None


def start_fake_rival(events_q, lines_q, verbose=True):
    """Background thread that prints every game event and answers a few with canned lines."""
    canned = {
        "bomb_hit": ("Boom. Was that the plan?", "gloating"),
        "streak": ("Okay... that's a lucky streak.", "rattled"),
        "pause": ("Taking a breather already?", "smug"),
        "game_over": ("I've seen better swordwork from a spoon.", "gloating"),
    }

    def loop():
        while True:
            ev = events_q.get()
            if verbose:
                print("[event]", ev, flush=True)
            if ev["type"] in canned:
                text, mood = canned[ev["type"]]
                time.sleep(0.4 if ev["type"] != "game_over" else 1.5)  # pretend to think
                try:
                    lines_q.put_nowait({"text": text, "mood": mood, "duration": 2.5})
                except queue.Full:
                    pass

    t = threading.Thread(target=loop, name="fake-rival", daemon=True)
    t.start()
    return t
