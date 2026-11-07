"""GRIP-9000's timing engine: decides IF and WHAT to say, never HOW.

The idea (same as a meetings voice agent): every event proposes a candidate
line with a priority. A candidate is only spoken if it clears the gates:

  1. state      - nothing during a pause (except pause lines), nothing after game over
  2. condition  - e.g. streaks only at milestones, combos only >= 4
  3. talking    - if a line is playing, a candidate must OUTRANK it to interrupt;
                  otherwise it is dropped (never queued: a stale heckle is worse than silence)
  4. global gap - 2.5 s of quiet after every line (bomb and game over skip this)
  5. cooldown   - per-rule, e.g. no two miss heckles within 5 s
  6. chance     - deliberate silence, e.g. only 45% of misses get a heckle

Pure logic: the caller passes 'now', and randomness comes from an injected
random.Random, so tests and replays are deterministic.
"""

import random

import shared

# key: (priority, cooldown_s, chance, skips_global_gap, source)
#   source: "bank"     - instant cached line
#           "prefetch" - pre-written Claude line if a fresh one is ready, else bank
#           "claude"   - live Claude line (1.8 s timeout, then bank)
RULES = {
    "game_over":          (100, 0.0, 1.00, True, "claude"),
    "bomb_hit":           (90, 4.0, 1.00, True, "prefetch"),
    "last_life":          (85, 0.0, 1.00, True, "claude"),
    "time_warning":       (70, 0.0, 1.00, False, "claude"),
    "streak":             (60, 8.0, 0.90, False, "bank"),
    "streak_big":         (60, 8.0, 0.90, False, "claude"),
    "combo":              (55, 6.0, 0.80, False, "bank"),
    "streak_broken":      (50, 6.0, 0.90, False, "prefetch"),
    "pause":              (45, 10.0, 0.70, False, "bank"),
    "pause_long":         (45, 0.0, 1.00, False, "bank"),
    "resume":             (40, 10.0, 0.50, False, "bank"),
    "halfway":            (36, 0.0, 1.00, False, "claude"),
    "pattern":            (35, 20.0, 1.00, False, "claude"),
    "miss":               (30, 5.0, 0.45, False, "prefetch"),
    "intro":              (20, 0.0, 1.00, False, "bank"),
    "slice":              (10, 12.0, 0.10, False, "bank"),
}

GLOBAL_GAP = 2.5            # seconds of quiet after a line ends
BOMB_SETTLE = 0.12          # wait this long after a bomb for its life_lost to arrive
PAUSE_GRACE = 1.5           # a resume within this is a flicker: say nothing
PAUSE_LONG = 8.0            # one follow-up taunt if still paused after this
RESUME_HUSH = 2.0           # gameplay heckles suppressed this long after resume
HUSH_BELOW_PRIORITY = 60    # ...for candidates below this priority
INTERRUPT_MIN_PRIORITY = 85 # only bomb, last life and game over may cut a line off mid-sentence
STREAK_MILESTONES = (5, 10, 15, 20, 25, 30)
BIG_STREAK = 10
MIN_COMBO = 4
MIN_STREAK_BROKEN = 5
PROVISIONAL_LINE_SECONDS = 3.0   # assumed length until the voice layer reports the real one


class Decision:
    """A line GRIP-9000 has decided to say. The voice layer turns it into audio."""

    def __init__(self, key, priority, mood, source, vars_, interrupt, final, t):
        self.key = key
        self.priority = priority
        self.mood = mood
        self.source = source
        self.vars = vars_
        self.interrupt = interrupt
        self.final = final
        self.t = t

    def __repr__(self):
        return ("Decision(" + self.key + ", p" + str(self.priority) + ", " + self.mood + ", "
                + self.source + (", INTERRUPT" if self.interrupt else "") + (", FINAL" if self.final else "")
                + ", " + str(self.vars) + ")")


class TimingEngine:
    def __init__(self, stats, rng=None, log=None):
        self.stats = stats
        self.rng = rng if rng is not None else random.Random()
        self.log = log if log is not None else (lambda now, text: None)
        self.reset_run()

    def reset_run(self):
        self.speaking_priority = None
        self.speaking_until = 0.0
        self.quiet_until = 0.0
        self.last_spoken = {}
        self.intro_done = False
        self.halfway_done = False
        self.over = False
        self.pending_bomb_at = None
        self.pending_pause_at = None
        self.pause_line_spoken = False
        self.pause_long_done = False

    # ------------------------------------------------------------------ events

    def on_event(self, event, now):
        """Call AFTER stats.update(event). Returns a Decision or None."""
        kind = event["type"]

        if kind == shared.GAME_START:
            self.reset_run()
            return self._consider("intro", {}, now)
        if self.over:
            self.log(now, "drop " + kind + ": run is over")
            return None
        if kind == shared.SWORD_DRAWN:
            return self._consider("intro", {}, now)
        if kind == shared.GAME_OVER:
            self.over = True
            self.pending_bomb_at = None
            self.pending_pause_at = None
            return self._consider("game_over", {
                "score": event["score"], "reason": event["reason"], "best_combo": event["best_combo"],
            }, now)
        if kind in (shared.BOMB_HIT, shared.LIFE_LOST):
            # Bomb and its life_lost arrive together; settle briefly so we know the lives left.
            if self.pending_bomb_at is None:
                self.pending_bomb_at = now + BOMB_SETTLE
            return None
        if kind == shared.PAUSE:
            if self.pending_pause_at is None and not self.pause_line_spoken:
                self.pending_pause_at = now + PAUSE_GRACE
            return None
        if kind == shared.RESUME:
            was_real_pause = self.pending_pause_at is None and self.pause_line_spoken
            if self.pending_pause_at is not None:
                self.log(now, "pause was a flicker (< " + str(PAUSE_GRACE) + " s): stay silent")
            self.pending_pause_at = None
            self.pause_line_spoken = False
            self.pause_long_done = False
            if was_real_pause:
                return self._consider("resume", {}, now)
            return None
        if self.stats.paused:
            self.log(now, "drop " + kind + ": paused")
            return None
        if kind == shared.TIME_WARNING:
            return self._consider("time_warning", {"seconds_left": event["seconds_left"]}, now)
        if kind == shared.STREAK:
            n = event["n"]
            if n not in STREAK_MILESTONES:
                return None
            if n >= BIG_STREAK:
                return self._consider("streak_big", {"n": n}, now)
            return self._consider("streak", {"n": n}, now)
        if kind == shared.COMBO:
            if event["n"] < MIN_COMBO:
                return None
            return self._consider("combo", {"n": event["n"]}, now)
        if kind == shared.STREAK_BROKEN:
            if event["n"] < MIN_STREAK_BROKEN:
                return None
            return self._consider("streak_broken", {"n": event["n"]}, now)
        if kind == shared.MISS:
            return self._consider("miss", {"side": event["side"], "n": self.stats.misses[event["side"]]}, now)
        if kind == shared.SLICE:
            return self._consider("slice", {"fruit": event["fruit"]}, now)
        return None

    # -------------------------------------------------------------------- tick

    def tick(self, now, patterns=None):
        """Call ~10 times a second. Resolves delayed candidates. Returns a Decision or None.

        patterns: list of (name, vars) from PatternDetector.check(), if it ran this tick.
        When a pattern Decision is returned, the caller must call
        detector.mark_spoken(decision.vars["pattern"]); unspoken patterns are offered again.
        """
        if self.over:
            return None

        if self.pending_bomb_at is not None and now >= self.pending_bomb_at:
            self.pending_bomb_at = None
            lives = self.stats.lives
            if lives <= 0:
                self.log(now, "bomb took the last life: leave it to the game over roast")
                return None
            if lives == 1:
                return self._consider("last_life", {"bombs": self.stats.bombs}, now)
            return self._consider("bomb_hit", {"lives": lives, "bombs": self.stats.bombs,
                                               "streak_was": self.stats.best_streak}, now)

        if self.pending_pause_at is not None and now >= self.pending_pause_at:
            self.pending_pause_at = None
            self.pause_line_spoken = True
            reason = self.stats.pause_reason or "not_gripping"
            return self._consider("pause", {"reason": reason}, now)

        if (self.stats.paused and self.pause_line_spoken and not self.pause_long_done
                and now - self.stats.pause_started >= PAUSE_LONG):
            self.pause_long_done = True
            return self._consider("pause_long", {"seconds": round(now - self.stats.pause_started)}, now)

        if self.stats.paused or not self.stats.running:
            return None

        if not self.halfway_done and self.stats.time_left(now) <= self.stats.duration / 2.0:
            self.halfway_done = True
            return self._consider("halfway", {"time_left": round(self.stats.time_left(now))}, now)

        if patterns:
            for name, vars_ in patterns:
                merged = {"pattern": name}
                for k in vars_:
                    merged[k] = vars_[k]
                decision = self._consider("pattern", merged, now)
                if decision is not None:
                    return decision
        return None

    # ------------------------------------------------------- voice layer hooks

    def line_started(self, decision, duration, now):
        """The voice layer reports the real length once audio starts."""
        if self.speaking_priority == decision.priority:
            self.speaking_until = now + duration
            self.quiet_until = self.speaking_until + GLOBAL_GAP

    def line_finished(self, now):
        """The voice layer reports audio ended (or was cut)."""
        self.speaking_priority = None
        self.speaking_until = now
        self.quiet_until = now + GLOBAL_GAP

    def is_speaking(self, now):
        return self.speaking_priority is not None and now < self.speaking_until

    # --------------------------------------------------------------- the gates

    def _consider(self, key, vars_, now):
        priority, cooldown, chance, skips_gap, source = RULES[key]

        if key == "intro":
            if self.intro_done:
                return None
            self.intro_done = True

        interrupt = False
        if self.is_speaking(now):
            if priority > self.speaking_priority and priority >= INTERRUPT_MIN_PRIORITY:
                interrupt = True
            else:
                self.log(now, "drop " + key + ": already saying something at p" + str(self.speaking_priority))
                return None

        if not interrupt and not skips_gap and now < self.quiet_until:
            self.log(now, "drop " + key + ": global gap (" + str(round(self.quiet_until - now, 1)) + " s left)")
            return None

        if (priority < HUSH_BELOW_PRIORITY and key != "resume"
                and now - self.stats.last_resume_t < RESUME_HUSH and self.stats.last_resume_t > self.stats.run_start):
            self.log(now, "drop " + key + ": hush after resume")
            return None

        last = self.last_spoken.get(key)
        if cooldown > 0 and last is not None and now - last < cooldown:
            self.log(now, "drop " + key + ": cooldown (" + str(round(cooldown - (now - last), 1)) + " s left)")
            return None

        if chance < 1.0 and self.rng.random() >= chance:
            self.log(now, "skip " + key + ": deliberate silence (" + str(round(chance * 100)) + "% chance)")
            return None

        self.last_spoken[key] = now
        self.speaking_priority = priority
        self.speaking_until = now + PROVISIONAL_LINE_SECONDS
        self.quiet_until = self.speaking_until + GLOBAL_GAP
        return Decision(key, priority, self._mood(key, vars_), source, vars_, interrupt, key == "game_over", now)

    def _mood(self, key, vars_):
        if key in ("streak", "streak_big", "combo"):
            return "rattled"
        if key == "pattern" and vars_.get("pattern") == "comeback":
            return "rattled"
        if key in ("miss", "bomb_hit", "last_life", "streak_broken", "pattern"):
            return "gloating"
        if key == "game_over":
            if vars_.get("new_best"):
                return "defensive"
            return "gloating"
        if key == "time_warning":
            if self.stats.lives == shared.LIVES and self.stats.current_streak >= 5:
                return "rattled"
            return "gloating"
        return "smug"
