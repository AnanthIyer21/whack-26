"""Game -> rival events.

Every event is a dict with "type" and "t" (time.monotonic()). Always build them
with the ev_* functions below, so a typo fails loudly at the call site, and send
them with post_event(), which never blocks.
"""

import queue
import time

events = queue.Queue()

GAME_START = "game_start"
SWORD_DRAWN = "sword_drawn"
SWORD_SHEATHED = "sword_sheathed"
SLICE = "slice"
MISS = "miss"
COMBO = "combo"
STREAK = "streak"
STREAK_BROKEN = "streak_broken"
BOMB_HIT = "bomb_hit"
LIFE_LOST = "life_lost"
PAUSE = "pause"
RESUME = "resume"
TIME_WARNING = "time_warning"
GAME_OVER = "game_over"

EVENT_TYPES = (
    GAME_START, SWORD_DRAWN, SWORD_SHEATHED, SLICE, MISS, COMBO, STREAK,
    STREAK_BROKEN, BOMB_HIT, LIFE_LOST, PAUSE, RESUME, TIME_WARNING, GAME_OVER,
)

PAUSE_REASONS = ("no_hand", "two_hands", "not_gripping")
MISS_SIDES = ("left", "right")
GAME_OVER_REASONS = ("lives", "timer", "quit")


def _make(event_type, **fields):
    event = {"type": event_type, "t": time.monotonic()}
    for key in fields:
        event[key] = fields[key]
    return event


def _check(value, allowed, name):
    if value not in allowed:
        raise ValueError(name + " must be one of " + str(allowed) + ", got " + repr(value))


def ev_game_start(duration, lives):
    """duration: run length in seconds (from settings); lives: starting lives."""
    return _make(GAME_START, duration=float(duration), lives=int(lives))


def ev_sword_drawn():
    return _make(SWORD_DRAWN)


def ev_sword_sheathed():
    return _make(SWORD_SHEATHED)


def ev_slice(fruit):
    """fruit: the fruit's name, e.g. "watermelon"."""
    return _make(SLICE, fruit=str(fruit))


def ev_miss(side):
    """A fruit fell off the bottom uncut. side: "left" or "right" half of the screen."""
    _check(side, MISS_SIDES, "side")
    return _make(MISS, side=side)


def ev_combo(n):
    return _make(COMBO, n=int(n))


def ev_streak(n):
    return _make(STREAK, n=int(n))


def ev_streak_broken(n):
    """n: the length of the streak that just ended."""
    return _make(STREAK_BROKEN, n=int(n))


def ev_bomb_hit():
    return _make(BOMB_HIT)


def ev_life_lost(lives_left):
    return _make(LIFE_LOST, lives_left=int(lives_left))


def ev_pause(reason):
    _check(reason, PAUSE_REASONS, "reason")
    return _make(PAUSE, reason=reason)


def ev_resume():
    return _make(RESUME)


def ev_time_warning(seconds_left):
    return _make(TIME_WARNING, seconds_left=int(seconds_left))


def ev_game_over(score, best_combo, duration, reason):
    _check(reason, GAME_OVER_REASONS, "reason")
    return _make(GAME_OVER, score=int(score), best_combo=int(best_combo),
                 duration=float(duration), reason=reason)


def post_event(event):
    """Send an event to the rival. Never blocks the game loop."""
    events.put_nowait(event)
