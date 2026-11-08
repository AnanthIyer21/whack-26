"""Game -> rival events, built with shared's ev_* builders and sent with post_event.

post_event never blocks (put_nowait on an unbounded queue). If sending ever fails, the
event is dropped and counted rather than crashing or stalling the game.
"""
from collections import deque

import shared
from . import sfx


class Emitter:
    def __init__(self, post_event):
        self.post = post_event
        self.dropped = 0
        self.log = deque(maxlen=300)    # recent events, for the debug overlay and tests

    def emit(self, type_, **fields):
        ev = getattr(shared, "ev_" + type_)(**fields)   # typos and bad fields fail loudly here
        try:
            self.post(ev)
        except Exception:
            self.dropped += 1
        self.log.append(ev)
        sfx.on_event(type_)               # sound effects (RBadiadka7)
        return ev

    def types(self):
        return [e["type"] for e in self.log]
