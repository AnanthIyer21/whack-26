"""Replay simulated 60 s runs through GRIP-9000's brain and print a timeline.

    python tools/fake_events.py                  # all four scenarios
    python tools/fake_events.py bad --seed 3     # one scenario, another random game
    python tools/fake_events.py good --quiet     # summary only
    python tools/fake_events.py --file logs/run.jsonl   # replay a recorded real game

Runs on a virtual clock (instant). Speech is simulated: bank lines take 2.4 s,
live Claude lines start after 1.5 s and take 3 s. Use it to tune agent/timing.py:
too chatty? raise GLOBAL_GAP or lower a chance. Too quiet? the opposite.
"""

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import shared  # noqa: E402
from agent.patterns import PatternDetector  # noqa: E402
from agent.stats import Stats  # noqa: E402
from agent.timing import TimingEngine  # noqa: E402

STEP = 0.05
BANK_SECONDS = 2.4
CLAUDE_DELAY = 1.5
CLAUDE_SECONDS = 3.0

SCENARIOS = {
    #            hit rate, left bias of misses, bomb hit rate, pause every (s), pause lengths
    "good":      (0.92, 0.5, 0.08, None, ()),
    "bad":       (0.60, 0.75, 0.25, 30.0, (3.0,)),
    "bombs":     (0.80, 0.5, 0.60, None, ()),
    "pausespam": (0.80, 0.5, 0.15, 7.0, (0.6, 0.9, 3.0, 10.0)),
}


def make_run(name, seed):
    """Build a list of (t, event) for one simulated run."""
    hit_rate, left_bias, bomb_rate, pause_every, pause_lengths = SCENARIOS[name]
    rng = random.Random(seed)
    out = []
    t = 0.0          # wall clock
    played = 0.0     # time actually in play
    lives = shared.LIVES
    streak = 0
    best_combo = 0
    score = 0
    next_pause = pause_every
    pause_index = 0
    warned = False

    def add(builder, *args):
        out.append((t, builder(*args)))

    add(shared.ev_game_start, 60, lives)
    t += 0.3
    add(shared.ev_sword_drawn)
    reason = "timer"
    while played < 60.0:
        gap = rng.uniform(0.5, 1.1)
        t += gap
        played += gap
        if played >= 60.0:
            break
        if not warned and played >= 50.0:
            warned = True
            add(shared.ev_time_warning, 10)
        if next_pause is not None and played >= next_pause:
            length = pause_lengths[pause_index % len(pause_lengths)]
            pause_index += 1
            reasons = ("not_gripping", "no_hand", "two_hands")
            add(shared.ev_pause, reasons[pause_index % 3])
            t += length
            add(shared.ev_resume)
            next_pause = played + pause_every
            continue
        if rng.random() < 0.16:
            # a bomb flies past
            if rng.random() < bomb_rate:
                add(shared.ev_bomb_hit)
                lives -= 1
                add(shared.ev_life_lost, lives)
                if streak >= 3:
                    add(shared.ev_streak_broken, streak)
                streak = 0
                if lives == 0:
                    reason = "lives"
                    break
            continue
        if rng.random() < hit_rate:
            fruit = rng.choice(("apple", "melon", "orange", "pineapple", "kiwi"))
            add(shared.ev_slice, fruit)
            score += 10
            streak += 1
            if streak % 5 == 0:
                add(shared.ev_streak, streak)
            if rng.random() < 0.12:
                n = rng.randint(3, 6)
                if n > best_combo:
                    best_combo = n
                score += n * 5
                add(shared.ev_combo, n)
        else:
            side = "left" if rng.random() < left_bias else "right"
            add(shared.ev_miss, side)
            if streak >= 3:
                add(shared.ev_streak_broken, streak)
            streak = 0
    add(shared.ev_sword_sheathed)
    add(shared.ev_game_over, score, best_combo, min(played, 60.0), reason)
    return out


def load_recording(path):
    out = []
    with open(path) as f:
        first_t = None
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if first_t is None:
                first_t = event["t"]
            out.append((event["t"] - first_t, event))
    return out


def simulate(timeline, seed, quiet):
    stats = Stats()
    rows = []

    def log(now, text):
        rows.append((now, "      . " + text))

    engine = TimingEngine(stats, rng=random.Random(seed), log=log)
    detector = PatternDetector()
    said = []
    speaking = None          # (decision, start, end)
    next_pattern_check = 0.0

    def handle(decision, now):
        nonlocal speaking
        if decision is None:
            return
        if speaking is not None and decision.interrupt:
            rows.append((now, "      x cut off: " + speaking[0].key))
        delay = CLAUDE_DELAY if decision.source == "claude" else 0.0
        length = CLAUDE_SECONDS if decision.source == "claude" else BANK_SECONDS
        engine.line_started(decision, delay + length, now)
        speaking = (decision, now + delay, now + delay + length)
        said.append((now, decision))
        extra = ""
        if decision.vars:
            extra = " " + json.dumps(decision.vars)
        rows.append((now, "  >>> SAY " + decision.key + " [" + decision.mood + ", " + decision.source
                     + (", interrupt" if decision.interrupt else "") + (", FINAL" if decision.final else "")
                     + "]" + extra))

    end = timeline[-1][0] + 6.0
    index = 0
    now = 0.0
    while now <= end:
        while index < len(timeline) and timeline[index][0] <= now:
            t, event = timeline[index]
            event = dict(event)
            event["t"] = t
            stats.update(event)
            rows.append((t, "  " + Stats._short(event)))
            handle(engine.on_event(event, t), t)
            if event["type"] == shared.GAME_START:
                detector.reset()
            index += 1
        if speaking is not None and now >= speaking[2]:
            engine.line_finished(now)
            speaking = None
        patterns = None
        if now >= next_pattern_check:
            next_pattern_check = now + 1.0
            patterns = detector.check(stats, now)
        decision = engine.tick(now, patterns)
        if decision is not None and decision.key == "pattern":
            detector.mark_spoken(decision.vars["pattern"])
        handle(decision, now)
        now += STEP

    if not quiet:
        for t, text in rows:
            print(("%6.1f" % t) + text)

    # summary
    gaps = []
    previous = 0.0
    for t, d in said:
        gaps.append(t - previous)
        previous = t
    drops = {}
    for t, text in rows:
        if text.startswith("      . "):
            reason = text[8:].split(":")[0] if ":" in text else text[8:]
            word = reason.split(" ")[0]
            detail = text[8:].split(": ")[-1].split(" (")[0]
            key = word + " - " + detail
            drops[key] = drops.get(key, 0) + 1
    claude = 0
    for t, d in said:
        if d.source == "claude":
            claude += 1
    print("")
    print("  lines spoken: " + str(len(said)) + "  (live Claude: " + str(claude) + ")")
    if gaps:
        print("  longest silence: " + str(round(max(gaps), 1)) + " s,  average gap: "
              + str(round(sum(gaps) / len(gaps), 1)) + " s")
    print("  not spoken, by reason:")
    for key in sorted(drops):
        print("     " + str(drops[key]).rjust(3) + "  " + key)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", choices=tuple(SCENARIOS) + ("all",), default="all")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--quiet", action="store_true", help="summary only")
    parser.add_argument("--file", help="replay a recorded JSONL event log instead")
    args = parser.parse_args()

    if args.file:
        print("=== recording: " + args.file)
        simulate(load_recording(args.file), args.seed, args.quiet)
        return
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for name in names:
        print("")
        print("=== scenario: " + name + "  (seed " + str(args.seed) + ")")
        simulate(make_run(name, args.seed), args.seed, args.quiet)


if __name__ == "__main__":
    main()
