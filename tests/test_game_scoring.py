import queue

from game.events import Emitter
from game.scoring import Score


def make():
    q = queue.Queue()
    ev = Emitter(q.put_nowait)
    return Score(ev), ev, q


def test_events_use_shared_builders_and_never_block():
    q = queue.Queue(maxsize=1)
    ev = Emitter(q.put_nowait)
    ev.emit("game_start", duration=60, lives=3)
    ev.emit("slice", fruit="kiwi")           # queue full: dropped, no exception, no block
    assert ev.dropped == 1
    e = q.get_nowait()
    assert e["type"] == "game_start" and isinstance(e["t"], float)
    assert e["duration"] == 60.0 and e["lives"] == 3


def test_bad_event_fields_fail_loudly():
    import pytest
    ev = Emitter(lambda e: None)
    with pytest.raises(ValueError):
        ev.emit("miss", side="middle")


def test_single_cuts_score_one_and_no_combo():
    s, ev, _ = make()
    s.cut(0.0, "apple")
    assert s.tick(1.0) is None
    s.cut(2.0, "kiwi")
    assert s.points == 2 and "combo" not in ev.types()


def test_three_in_a_swing_is_combo_with_bonus():
    s, ev, _ = make()
    for t in (0.0, 0.1, 0.2):
        s.cut(t, "orange")
    assert s.tick(0.3) is None               # gap not over yet
    c = s.tick(0.46)
    assert c.n == 3 and c.name == "NICE" and c.bonus == 3
    assert s.points == 3 + 3 and s.best_combo == 3
    assert [e for e in ev.log if e["type"] == "combo"][0]["n"] == 3


def test_two_in_a_swing_is_nothing_special():
    s, ev, _ = make()
    s.cut(0.0, "kiwi")
    s.cut(0.1, "kiwi")
    assert s.tick(0.5) is None and s.points == 2
    assert "combo" not in ev.types() and s.best_combo == 2


def test_combo_tiers_escalate():
    from game.scoring import tier_for
    assert tier_for(1) is None and tier_for(2) is None
    assert [tier_for(n).bonus for n in (3, 4, 5, 6, 7, 8)] == [3, 6, 10, 15, 20, 25]
    assert [tier_for(n).name for n in (4, 5, 6, 9)] == ["GREAT", "SAVAGE", "UNREAL", "UNREAL"]


def test_streak_events_and_multiplier():
    s, ev, _ = make()
    for i in range(12):
        s.cut(i * 1.0, "lemon")
    streaks = [e["n"] for e in ev.log if e["type"] == "streak"]
    assert streaks == [5, 10]
    assert s.points == 4 * 1 + 5 * 2 + 3 * 3     # x1 for 1-4, x2 for 5-9, x3 for 10-12
    assert s.multiplier == 3


def test_multiplier_steps_and_progress():
    from game.scoring import multiplier, mult_progress
    assert [multiplier(n) for n in (0, 4, 5, 9, 10, 17, 18, 27, 28, 99)] == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert mult_progress(0) == (1, 0.0) and mult_progress(7) == (2, 0.4)
    assert mult_progress(14) == (3, 0.5) and mult_progress(40) == (5, 1.0)


def test_miss_resets_multiplier():
    s, ev, _ = make()
    for i in range(7):
        s.cut(i * 1.0, "kiwi")
    s.miss("left")
    assert s.multiplier == 1


def test_miss_breaks_streak_and_reports_side():
    s, ev, _ = make()
    for i in range(6):
        s.cut(i * 1.0, "lemon")
    s.miss("left")
    assert s.streak == 0
    assert ev.types()[-2:] == ["miss", "streak_broken"]
    assert ev.log[-2]["side"] == "left" and ev.log[-1]["n"] == 6


def test_short_streak_break_is_silent():
    s, ev, _ = make()
    s.cut(0, "kiwi")
    s.miss("right")
    assert "streak_broken" not in ev.types()


def test_bomb_costs_life_and_emits_in_order():
    s, ev, _ = make()
    assert s.bomb() == 2
    assert ev.types() == ["bomb_hit", "life_lost"]
    assert ev.log[-1]["lives_left"] == 2
    s.bomb()
    assert s.bomb() == 0 and s.bomb() == 0   # never negative
