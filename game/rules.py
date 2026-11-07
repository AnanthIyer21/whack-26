"""Score, combos, streaks and lives. Pure logic, no pygame, unit-tested.

Every method returns a list of events (dicts with "type" and fields, no "t");
the play scene sends them to the rival.
"""
from game import config


class Rules:
    def __init__(self):
        self.score = 0
        self.lives = config.LIVES
        self.streak = 0
        self.best_combo = 0
        self.run = 0            # cuts in the current combo run
        self.last_cut = None    # time of the last cut in the run
        self.over = False
        self.multiplier = 1     # for peace sign later

    def on_cut(self, fruit, points, now):
        events = []
        if self.run and now - self.last_cut > config.COMBO_GAP:
            events += self.settle()
        self.score += points * self.multiplier
        self.run += 1
        self.last_cut = now
        self.best_combo = max(self.best_combo, self.run)
        events.append({"type": "slice", "fruit": fruit})
        self.streak += 1
        if self.streak % config.STREAK_STEP == 0:
            events.append({"type": "streak", "n": self.streak})
        return events

    def update(self, now):
        """Call every frame: ends the combo run once COMBO_GAP passes with no cut."""
        if self.run and now - self.last_cut > config.COMBO_GAP:
            return self.settle()
        return []

    def settle(self):
        """Finish the current run; pays out a combo if it was big enough."""
        n, self.run, self.last_cut = self.run, 0, None
        if n >= config.COMBO_MIN:
            self.score += n
            return [{"type": "combo", "n": n}]
        return []

    def on_drop(self, fruit, side):
        if self.over:
            return []
        events = [{"type": "miss", "fruit": fruit, "side": side}]
        if self.streak >= config.STREAK_STEP:
            events.append({"type": "streak_broken", "n": self.streak})
        self.streak = 0
        self.lives -= 1
        events.append({"type": "life_lost", "lives_left": self.lives})
        if self.lives <= 0:
            self.over = True
        return events
