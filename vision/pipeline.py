"""One frame in, one HandState out. No threads, no camera: easy to test and time."""
import math
import time

from vision import geometry
from vision.stabiliser import GRIP, OPEN, UNCLEAR, BladeSmoother, GripStabiliser, HandCounter
from vision.tracker import HandTracker

UP = -math.pi / 2


class VisionPipeline:
    def __init__(self, width, height, tracker=None):
        self.width, self.height = width, height
        self.tracker = tracker or HandTracker()
        self.counter = HandCounter()
        self.grip = GripStabiliser()
        self.blade = BladeSmoother()
        self._last_base = (0.5, 0.5)
        self._last_angle = UP
        self._last_score = 0.0
        self._last_curls = None
        self._last_n = 0

    def process(self, rgb, t):
        """rgb: mirrored RGB frame; t: time.monotonic() at capture.

        Returns (fields, debug). fields are exactly HandState's fields.
        """
        p0 = time.perf_counter()
        hands = self.tracker.detect(rgb, t)
        p1 = time.perf_counter()

        sword, count, held = self.counter.update(hands, t)
        if self.counter.lost:
            self.grip.reset()
            self.blade.reset()

        raw_angle = foreshorten = norm = None
        if sword is not None and not held:
            # Canonical hand frame (wrist origin, palm = 1, left mirrored to right),
            # kept for the debug view and future gestures. The curl maths below uses
            # metric world landmarks, which give the same answer for either hand.
            norm = geometry.normalise(sword.img, sword.label)
            score, curls, n = geometry.curl_score(sword.world)
            self._last_score, self._last_curls, self._last_n = score, curls, n
            p2 = time.perf_counter()
            self.grip.update(score, n)
            raw_base = geometry.blade_base(sword.img)
            raw_angle = geometry.blade_angle(sword.img, self.width, self.height)
            foreshorten = geometry.foreshortening(sword.world)
            self._last_base, self._last_angle = self.blade.update(raw_base, raw_angle, foreshorten, t)
        else:
            p2 = time.perf_counter()
        p3 = time.perf_counter()

        tracked = sword is not None
        state = self.grip.state if tracked else None
        certainty = geometry.grip_certainty(self._last_score) if tracked else 0.0
        fields = dict(
            sword_visible=tracked,
            # Forced off with two hands in frame, so the game can't play on.
            sword_active=tracked and state == GRIP and count == 1,
            blade_base=self._last_base,
            blade_angle=self._last_angle,
            hands_in_frame=count,
            gesture="none",
            confidence=(sword.score * certainty) if tracked else 0.0,
            t=t,
        )
        debug = dict(
            hands=hands, sword=sword, held=held, grip_state=state,
            score=self._last_score if tracked else None,
            curls=self._last_curls if tracked else None, n_curled=self._last_n,
            raw_angle=raw_angle, foreshorten=foreshorten, side_on=self.blade.side_on, norm=norm,
            ms=dict(mediapipe=(p1 - p0) * 1e3, grip=(p2 - p1) * 1e3, smooth=(p3 - p2) * 1e3),
        )
        return fields, debug

    def close(self):
        self.tracker.close()
