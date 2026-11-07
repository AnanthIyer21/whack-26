"""Fake rival: prints every event and answers some with a canned line.

Shows the rival-side contract: drain shared.events without blocking for long,
push subtitles to shared.rival_lines, set shared.rival_speaking while "talking".
"""

import queue
import time

import shared

CANNED = {
    "game_start": ("GRIP-9000 online. Try not to embarrass your species.", "smug"),
    "miss": ("Gravity: one. You: nil.", "gloating"),
    "bomb_hit": ("You hugged the bomb. Bold.", "gloating"),
    "streak": ("That is statistically irritating.", "rattled"),
    "pause": ("Paused? Calling for backup?", "smug"),
    "game_over": ("Run terminated. As predicted.", "gloating"),
}
SPEAK_SECONDS = 2.0


def run(stop_event, offline=False):
    speaking_until = 0.0
    while not stop_event.is_set():
        now = time.monotonic()
        if shared.rival_speaking.is_set() and now >= speaking_until:
            shared.rival_speaking.clear()
        try:
            event = shared.events.get(timeout=0.05)
        except queue.Empty:
            continue
        lag_ms = (time.monotonic() - event["t"]) * 1000.0
        print("[fake rival] " + event["type"] + " " + str(event) + "  (lag " + str(round(lag_ms, 1)) + " ms)")
        if event["type"] in CANNED:
            text, mood = CANNED[event["type"]]
            is_final = event["type"] == "game_over"
            shared.post_rival_line(text, mood, SPEAK_SECONDS, final=is_final)
            shared.rival_speaking.set()
            speaking_until = time.monotonic() + SPEAK_SECONDS
    shared.rival_speaking.clear()
