"""Game -> rival events. Every event is a dict with "type" and "t" (time.monotonic()).

put_nowait only: the game never blocks on the rival. If the queue is ever full (it shouldn't
be), the event is dropped and counted.
"""
from collections import deque
import queue
import time


class Emitter:
    def __init__(self, q, clock=time.monotonic):
        self.q = q
        self.clock = clock
        self.dropped = 0
        self.log = deque(maxlen=300)    # recent events, for the debug overlay and tests

    def emit(self, type_, **fields):
        ev = {"type": type_, "t": self.clock(), **fields}
        try:
            self.q.put_nowait(ev)
        except queue.Full:
            self.dropped += 1
        self.log.append(ev)
        return ev

    def types(self):
        return [e["type"] for e in self.log]
