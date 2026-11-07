"""Rules of GRIP-9000's timing engine. Run: python -m pytest -q"""

import random

import shared
from agent.stats import Stats
from agent.timing import TimingEngine, GLOBAL_GAP, PAUSE_GRACE, BOMB_SETTLE, PAUSE_LONG


class AlwaysTalk(random.Random):
    """Chance gates always pass (random() returns 0)."""
    def random(self):
        return 0.0


class NeverTalk(random.Random):
    def random(self):
        return 0.999


def ev(builder, t, *args):
    event = builder(*args)
    event["t"] = t
    return event


def setup(rng=None):
    stats = Stats()
    engine = TimingEngine(stats, rng=rng or AlwaysTalk())
    return stats, engine


def feed(stats, engine, event):
    stats.update(event)
    return engine.on_event(event, event["t"])


def start(stats, engine, t=0.0):
    d = feed(stats, engine, ev(shared.ev_game_start, t, 60, 3))
    engine.line_finished(t + 1.0)   # intro finished
    return d


def test_intro_spoken_once():
    stats, engine = setup()
    d = start(stats, engine)
    assert d is not None and d.key == "intro"
    assert feed(stats, engine, ev(shared.ev_sword_drawn, 10.0)) is None


def test_global_gap_blocks_back_to_back_lines():
    stats, engine = setup()
    start(stats, engine)
    first = feed(stats, engine, ev(shared.ev_miss, 10.0, "left"))
    assert first is not None
    engine.line_started(first, 1.5, 10.0)
    engine.line_finished(11.5)
    # inside the gap: dropped
    assert feed(stats, engine, ev(shared.ev_combo, 11.5 + GLOBAL_GAP - 0.1, 5)) is None
    # after the gap: allowed
    assert feed(stats, engine, ev(shared.ev_combo, 11.5 + GLOBAL_GAP + 0.1, 5)) is not None


def test_bomb_interrupts_miss_heckle():
    stats, engine = setup()
    start(stats, engine)
    miss = feed(stats, engine, ev(shared.ev_miss, 10.0, "left"))
    engine.line_started(miss, 2.0, 10.0)
    assert feed(stats, engine, ev(shared.ev_bomb_hit, 10.5)) is None       # settling
    assert feed(stats, engine, ev(shared.ev_life_lost, 10.51, 2)) is None
    d = engine.tick(10.5 + BOMB_SETTLE + 0.01)
    assert d is not None and d.key == "bomb_hit" and d.interrupt


def test_lower_priority_is_dropped_not_queued():
    stats, engine = setup()
    start(stats, engine)
    bomb = feed(stats, engine, ev(shared.ev_bomb_hit, 10.0))
    feed(stats, engine, ev(shared.ev_life_lost, 10.0, 2))
    bomb = engine.tick(10.2)
    engine.line_started(bomb, 2.0, 10.2)
    assert feed(stats, engine, ev(shared.ev_miss, 10.5, "right")) is None


def test_bomb_on_last_life_becomes_last_life_line():
    stats, engine = setup()
    start(stats, engine)
    feed(stats, engine, ev(shared.ev_bomb_hit, 10.0))
    feed(stats, engine, ev(shared.ev_life_lost, 10.01, 1))
    d = engine.tick(10.2)
    assert d.key == "last_life" and d.source == "claude"


def test_bomb_taking_final_life_leaves_it_to_game_over():
    stats, engine = setup()
    start(stats, engine)
    feed(stats, engine, ev(shared.ev_bomb_hit, 10.0))
    feed(stats, engine, ev(shared.ev_life_lost, 10.01, 0))
    assert engine.tick(10.2) is None


def test_flicker_pause_is_silent():
    stats, engine = setup()
    start(stats, engine)
    assert feed(stats, engine, ev(shared.ev_pause, 10.0, "not_gripping")) is None
    assert feed(stats, engine, ev(shared.ev_resume, 10.0 + PAUSE_GRACE - 0.2)) is None
    assert engine.tick(10.0 + PAUSE_GRACE + 0.5) is None


def test_real_pause_mocked_by_reason_then_follow_up():
    stats, engine = setup()
    start(stats, engine)
    feed(stats, engine, ev(shared.ev_pause, 10.0, "two_hands"))
    d = engine.tick(10.0 + PAUSE_GRACE + 0.01)
    assert d.key == "pause" and d.vars["reason"] == "two_hands"
    engine.line_finished(13.0)
    d2 = engine.tick(10.0 + PAUSE_LONG + 0.1)
    assert d2 is not None and d2.key == "pause_long"


def test_heckles_hushed_right_after_resume():
    """The hush matters when the resume quip was skipped (so there is no global gap)."""
    stats, engine = setup()
    start(stats, engine)
    feed(stats, engine, ev(shared.ev_pause, 10.0, "no_hand"))
    engine.tick(12.0)
    engine.line_finished(13.0)
    engine.rng = NeverTalk()                      # resume quip skipped (50% chance)
    assert feed(stats, engine, ev(shared.ev_resume, 20.0)) is None
    engine.rng = AlwaysTalk()
    assert feed(stats, engine, ev(shared.ev_miss, 21.0, "left")) is None      # hushed
    assert feed(stats, engine, ev(shared.ev_miss, 22.5, "left")) is not None  # hush over


def test_deliberate_silence():
    stats, engine = setup(NeverTalk())
    start(stats, engine)
    assert feed(stats, engine, ev(shared.ev_miss, 10.0, "left")) is None


def test_streak_only_at_milestones_and_big_ones_use_claude():
    stats, engine = setup()
    start(stats, engine)
    assert feed(stats, engine, ev(shared.ev_streak, 10.0, 7)) is None
    d = feed(stats, engine, ev(shared.ev_streak, 10.0, 10))
    assert d.key == "streak_big" and d.source == "claude" and d.mood == "rattled"


def test_game_over_always_speaks_and_is_final():
    stats, engine = setup(NeverTalk())
    start(stats, engine)
    feed(stats, engine, ev(shared.ev_bomb_hit, 10.0))
    feed(stats, engine, ev(shared.ev_life_lost, 10.0, 2))
    bomb = engine.tick(10.2)
    engine.line_started(bomb, 3.0, 10.2)
    d = feed(stats, engine, ev(shared.ev_game_over, 10.5, 90, 2, 10.5, "quit"))
    assert d.key == "game_over" and d.final and d.interrupt
    assert feed(stats, engine, ev(shared.ev_miss, 11.0, "left")) is None


def test_halfway_fires_once():
    stats, engine = setup()
    start(stats, engine)
    d = engine.tick(30.5)
    assert d is not None and d.key == "halfway"
    engine.line_finished(33.0)
    assert engine.tick(40.0) is None


def test_small_moments_do_not_cut_lines_off():
    stats, engine = setup()
    d = start(stats, engine)
    intro = feed(stats, engine, ev(shared.ev_game_start, 100.0, 60, 3))
    engine.line_started(intro, 3.0, 100.0)
    assert feed(stats, engine, ev(shared.ev_miss, 100.9, "left")) is None
    assert feed(stats, engine, ev(shared.ev_streak, 101.0, 10)) is None


def test_unspoken_pattern_is_offered_again():
    from agent.patterns import PatternDetector
    stats, engine = setup()
    detector = PatternDetector()
    start(stats, engine)
    for t in (5.0, 6.0, 7.0):
        stats.update(ev(shared.ev_miss, t, "left"))
    found = detector.check(stats, 7.5)
    names = []
    for name, vars_ in found:
        names.append(name)
    assert "side_bias" in names
    # not marked spoken -> still offered
    found_again = detector.check(stats, 8.5)
    names_again = []
    for name, vars_ in found_again:
        names_again.append(name)
    assert "side_bias" in names_again
    detector.mark_spoken("side_bias")
    for name, vars_ in detector.check(stats, 9.5):
        assert name != "side_bias"
