"""Live stats about the current run, built only from game events.

The rival reads these to pick lines and to give Claude something specific to roast.
Every update takes the event's own "t", so replays with a fake clock work the same.
"""

from collections import deque

import shared


class Stats:
    def __init__(self):
        self.reset(0.0, float(shared.DEFAULT_RUN_SECONDS), shared.LIVES)
        self.runs_this_session = 0

    def reset(self, t, duration, lives):
        self.running = False
        self.over = False
        self.run_start = t
        self.duration = duration
        self.lives = lives
        self.slices = 0
        self.score_estimate = 0
        self.final_score = None
        self.misses = {"left": 0, "right": 0}
        self.bombs = 0
        self.bomb_times = []
        self.current_streak = 0
        self.streak_start_t = t
        self.best_streak = 0
        self.best_combo = 0
        self.pauses = {"no_hand": 0, "two_hands": 0, "not_gripping": 0}
        self.paused = False
        self.pause_reason = None
        self.pause_started = 0.0
        self.paused_total = 0.0
        self.last_resume_t = t
        self.last_slice_t = t
        self.last_life_lost_t = None
        self.game_over_reason = None
        self.recent = deque(maxlen=5)

    # --- updates ---

    def update(self, event):
        kind = event["type"]
        t = event["t"]
        self.recent.append(self._short(event))

        if kind == shared.GAME_START:
            self.reset(t, event.get("duration", float(shared.DEFAULT_RUN_SECONDS)), event.get("lives", shared.LIVES))
            self.running = True
            self.runs_this_session += 1
            self.recent.append(self._short(event))
        elif kind == shared.SLICE:
            self.slices += 1
            self.score_estimate += 10
            if self.current_streak == 0:
                self.streak_start_t = t
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
            self.last_slice_t = t
        elif kind == shared.MISS:
            self.misses[event["side"]] += 1
            self.current_streak = 0
        elif kind == shared.COMBO:
            if event["n"] > self.best_combo:
                self.best_combo = event["n"]
        elif kind == shared.STREAK:
            if event["n"] > self.best_streak:
                self.best_streak = event["n"]
        elif kind == shared.STREAK_BROKEN:
            self.current_streak = 0
        elif kind == shared.BOMB_HIT:
            self.bombs += 1
            self.bomb_times.append(t)
            self.current_streak = 0
        elif kind == shared.LIFE_LOST:
            self.lives = event["lives_left"]
            self.last_life_lost_t = t
        elif kind == shared.PAUSE:
            if not self.paused:
                self.paused = True
                self.pause_started = t
            self.pause_reason = event["reason"]
            self.pauses[event["reason"]] += 1
        elif kind == shared.RESUME:
            if self.paused:
                self.paused_total += t - self.pause_started
            self.paused = False
            self.pause_reason = None
            self.last_resume_t = t
        elif kind == shared.GAME_OVER:
            self.running = False
            self.over = True
            self.final_score = event["score"]
            if event["best_combo"] > self.best_combo:
                self.best_combo = event["best_combo"]
            self.game_over_reason = event["reason"]

    # --- derived values ---

    def time_left(self, now):
        played = now - self.run_start - self.paused_total
        if self.paused:
            played -= now - self.pause_started
        left = self.duration - played
        if left < 0:
            return 0.0
        return left

    def total_misses(self):
        return self.misses["left"] + self.misses["right"]

    def score(self):
        if self.final_score is not None:
            return self.final_score
        return self.score_estimate

    def accuracy(self):
        attempts = self.slices + self.total_misses()
        if attempts == 0:
            return None
        return self.slices / attempts

    def snapshot(self, now):
        """A compact, JSON-friendly view for Claude and for logs."""
        accuracy = self.accuracy()
        return {
            "score": self.score(),
            "slices": self.slices,
            "misses_left": self.misses["left"],
            "misses_right": self.misses["right"],
            "accuracy_pct": None if accuracy is None else round(accuracy * 100),
            "bombs_hit": self.bombs,
            "lives": self.lives,
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "best_combo": self.best_combo,
            "pauses": sum(self.pauses.values()),
            "seconds_paused": round(self.paused_total),
            "time_left": round(self.time_left(now)),
            "run_number_this_session": self.runs_this_session,
            "recent": list(self.recent),
        }

    @staticmethod
    def _short(event):
        kind = event["type"]
        if kind == shared.MISS:
            return "miss(" + event["side"] + ")"
        if kind in (shared.COMBO, shared.STREAK, shared.STREAK_BROKEN):
            return kind + "(" + str(event["n"]) + ")"
        if kind == shared.PAUSE:
            return "pause(" + event["reason"] + ")"
        if kind == shared.LIFE_LOST:
            return "life_lost(" + str(event["lives_left"]) + " left)"
        return kind
