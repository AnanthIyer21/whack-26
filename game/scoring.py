"""Points, combos, streaks and lives. Pure logic (no pygame), so it's unit tested.

  - Streak multiplier: each fruit scores x1, then x2 from 5 in a row, x3 from 10, x4 from 18,
    x5 from 28.
    A miss or bomb drops you back to x1.
  - Swing = cuts with no gap over 0.25 s. Multi-fruit swings earn tiered bonuses:
        3 NICE +3 | 4 GREAT +6 | 5 SAVAGE +10 | 6 UNREAL +15 | 7+ +5 more each
    3+ fruit also sends a 'combo' event (n) when the swing ends.
  - Streak = fruit cut in a row. 'streak' event at 5, 10, 15 ...  A miss or a bomb breaks it
    ('streak_broken' only if it was 5+).
  - 3 lives; each bomb costs one ('bomb_hit' then 'life_lost').
"""

from dataclasses import dataclass

COMBO_GAP = 0.25
COMBO_MIN = 3          # smallest swing that counts as a 'combo' event for the rival
# (min fruit, name, bonus, colour)
TIERS = (
    (3, "NICE", 3, (255, 230, 90)),
    (4, "GREAT", 6, (255, 175, 60)),
    (5, "SAVAGE", 10, (255, 95, 70)),
    (6, "UNREAL", 15, (225, 120, 255)),
)


def multiplier(streak):
    m = 1
    for i, need in enumerate(MULT_STEPS):
        if streak >= need:
            m = i + 1
    return m


def mult_progress(streak):
    """(multiplier, 0..1 progress to the next one) - the HUD's streak meter."""
    m = multiplier(streak)
    if m >= len(MULT_STEPS):
        return m, 1.0
    lo, hi = MULT_STEPS[m - 1], MULT_STEPS[m]
    return m, (streak - lo) / (hi - lo)


@dataclass(frozen=True)
class Combo:
    n: int
    name: str
    bonus: int
    color: tuple


def tier_for(n):
    """The combo tier for a swing of n fruit, or None for a single cut."""
    best = None
    for min_n, name, bonus, color in TIERS:
        if n >= min_n:
            best = (name, bonus, color)
    if best is None:
        return None
    name, bonus, color = best
    if n > TIERS[-1][0]:
        bonus += 5 * (n - TIERS[-1][0])
    return Combo(n, name, bonus, color)
STREAK_STEP = 5
MULT_STEPS = (0, 5, 10, 18, 28)    # streak needed for x1, x2, x3, x4, x5
STREAK_BROKEN_MIN = 5
START_LIVES = 3


class Score:
    def __init__(self, emitter, lives=START_LIVES):
        self.ev = emitter
        self.points = 0
        self.max_lives = lives
        self.lives = lives
        self.streak = 0
        self.best_combo = 0      # most fruit in one swing
        self.swing = 0
        self.last_cut = None

    @property
    def multiplier(self):
        return multiplier(self.streak)

    def cut(self, t, fruit_name):
        """A fruit was sliced. Returns the points it scored (combo bonus comes at swing end)."""
        self.tick(t)
        self.streak += 1
        pts = self.multiplier
        self.points += pts
        self.swing += 1
        self.last_cut = t
        self.ev.emit("slice", fruit=fruit_name)
        if self.streak % STREAK_STEP == 0:
            self.ev.emit("streak", n=self.streak)
        return pts

    def tick(self, t):
        """Call every frame. Returns a Combo when a multi-fruit swing just finished, else None."""
        if self.swing and t - self.last_cut > COMBO_GAP:
            return self._end_swing()
        return None

    def _end_swing(self):
        n, self.swing = self.swing, 0
        self.best_combo = max(self.best_combo, n)
        combo = tier_for(n)
        if combo:
            self.points += combo.bonus
            if n >= COMBO_MIN:
                self.ev.emit("combo", n=n)
        return combo

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
        """Close any open swing at the end of the run. Returns a final Combo or None."""
        return self._end_swing() if self.swing else None

    def _break_streak(self):
        if self.streak >= STREAK_BROKEN_MIN:
            self.ev.emit("streak_broken", n=self.streak)
        self.streak = 0
