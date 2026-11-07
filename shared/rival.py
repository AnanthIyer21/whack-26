"""Rival -> game: subtitles for the speech bubble and avatar, plus the ducking flag.

rival_lines carries dicts:
    {"text": str, "mood": "smug" | "rattled" | "defensive" | "gloating",
     "duration": seconds, "final": bool (optional)}
A line is pushed the moment its audio starts. The game shows only the newest
line. "final": True marks the game over roast for the game over screen.

rival_speaking is set while the rival's voice is playing; the game multiplies
its own sound volumes by DUCK_LEVEL while it is set.
"""

import queue
import threading

from shared.constants import MOODS

rival_lines = queue.Queue()
rival_speaking = threading.Event()


def post_rival_line(text, mood, duration, final=False):
    if mood not in MOODS:
        raise ValueError("mood must be one of " + str(MOODS) + ", got " + repr(mood))
    line = {"text": str(text), "mood": mood, "duration": float(duration)}
    if final:
        line["final"] = True
    rival_lines.put_nowait(line)
