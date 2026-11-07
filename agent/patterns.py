"""Rule-based habit detection: the call-outs that prove GRIP-9000 is watching.

check() is called about once a second during play and returns every pattern that
is currently true and not yet spoken. A pattern only counts as used once the
caller reports it was actually said (mark_spoken), so a call-out that lands
while GRIP-9000 is busy is offered again later instead of being lost.
Each pattern is spoken once per run, except slump, which re-arms after the next slice.
"""

SLUMP_SECONDS = 6.0
BOMB_MAGNET_WINDOW = 15.0


class PatternDetector:
    def __init__(self):
        self.reset()

    def reset(self):
        self.fired = set()
        self.slump_armed = True
        self.last_slice_seen = 0.0

    def check(self, stats, now):
        """Returns a list of (pattern_name, vars) currently true and not yet spoken."""
        found = []
        if not stats.running or stats.paused:
            return found

        # Side bias: >= 3 misses on one side and at least twice the other side.
        for side, other in (("left", "right"), ("right", "left")):
            n = stats.misses[side]
            if n >= 3 and n >= 2 * stats.misses[other] and "side_bias" not in self.fired:
                found.append(("side_bias", {"side": side, "n": n, "other_n": stats.misses[other]}))

        # Bomb magnet: two bombs within 15 seconds.
        if len(stats.bomb_times) >= 2 and "bomb_magnet" not in self.fired:
            gap = stats.bomb_times[-1] - stats.bomb_times[-2]
            if gap <= BOMB_MAGNET_WINDOW:
                found.append(("bomb_magnet", {"n": stats.bombs, "gap": round(gap)}))

        # Pause addict: three or more pauses this run.
        total_pauses = 0
        for reason in stats.pauses:
            total_pauses += stats.pauses[reason]
        if total_pauses >= 3 and "pause_addict" not in self.fired:
            found.append(("pause_addict", {"n": total_pauses}))

        # Slump: no slice for 6 s of actual play. Re-arms after the next slice.
        if stats.last_slice_t != self.last_slice_seen:
            self.last_slice_seen = stats.last_slice_t
            self.slump_armed = True
        since = now - max(stats.last_slice_t, stats.last_resume_t, stats.run_start)
        if self.slump_armed and since >= SLUMP_SECONDS:
            found.append(("slump", {"seconds": round(since)}))

        # Comeback: a streak of 5+ built after losing a life.
        if (stats.last_life_lost_t is not None and stats.current_streak >= 5
                and stats.streak_start_t > stats.last_life_lost_t and "comeback" not in self.fired):
            found.append(("comeback", {"streak": stats.current_streak, "lives": stats.lives}))

        return found

    def mark_spoken(self, name):
        if name == "slump":
            self.slump_armed = False
        else:
            self.fired.add(name)
