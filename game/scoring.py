"""Points, combos, streaks and lives. Pure logic (no pygame), so it's unit tested.

  - 1 point per fruit; x2 while the streak is 10 or more.
  - Swing = cuts with no gap over 0.25 s. 3+ fruit in one swing = combo: bonus +n points,
    'combo' event when the swing ends.
  - Streak = fruit cut in a row. 'streak' event at 5, 10, 15 ...  A miss or a bomb breaks it
    ('streak_broken' only if it was 5+).
  - 3 lives; each bomb costs one ('bomb_hit' then 'life_lost').
"""

COMBO_GAP = 0.25
COMBO_MIN = 3
STREAK_STEP = 5
STREAK_DOUBLE_AT = 10
STREAK_BROKEN_MIN = 5
START_LIVES = 3


class Score:
    def __init__(self, emitter):
        self.ev = emitter
        self.points = 0
        self.lives = START_LIVES
        self.streak = 0
        self.best_combo = 0      # most fruit in one swing
        self.swing = 0
        self.last_cut = None

    @property
    def doubled(self):
        return self.streak >= STREAK_DOUBLE_AT

    def cut(self, t, fruit_name):
        """A fruit was sliced. Returns the points it scored (combo bonus comes at swing end)."""
        self.tick(t)
        self.streak += 1
        pts = 2 if self.doubled else 1
        self.points += pts
        self.swing += 1
        self.last_cut = t
        self.ev.emit("slice", fruit=fruit_name)
        if self.streak % STREAK_STEP == 0:
            self.ev.emit("streak", n=self.streak)
        return pts

    def tick(self, t):
        """Call every frame. Returns the combo size if a combo just finished, else 0."""
        if self.swing and t - self.last_cut > COMBO_GAP:
            return self._end_swing()
        return 0

    def _end_swing(self):
        n, self.swing = self.swing, 0
        self.best_combo = max(self.best_combo, n)
        if n >= COMBO_MIN:
            self.points += n
            self.ev.emit("combo", n=n)
            return n
        return 0

    def miss(self, side):
        self.ev.emit("miss", side=side)
        self._break_streak()

    def bomb(self):
        """Returns lives left."""
        if self.swing:
            self._end_swing()
        self.ev.emit("bomb_hit")
        self._break_streak()
        self.lives = max(0, self.lives - 1)
        self.ev.emit("life_lost", lives_left=self.lives)
        return self.lives

    def finish(self):
        """Close any open swing at the end of the run. Returns a final combo size or 0."""
        return self._end_swing() if self.swing else 0

    def _break_streak(self):
        if self.streak >= STREAK_BROKEN_MIN:
            self.ev.emit("streak_broken", n=self.streak)
        self.streak = 0
