import queue

from game.events import Emitter
from game.scoring import Score


def make():
    q = queue.Queue()
    t = [0.0]
    ev = Emitter(q, clock=lambda: t[0])
    return Score(ev), ev, q


def test_events_have_type_and_t_and_never_block():
    q = queue.Queue(maxsize=1)
    ev = Emitter(q)
    ev.emit("game_start")
    ev.emit("slice", fruit="kiwi")           # queue full: dropped, no exception, no block
    assert ev.dropped == 1
    e = q.get_nowait()
    assert e["type"] == "game_start" and isinstance(e["t"], float)


def test_single_cuts_score_one_and_no_combo():
    s, ev, _ = make()
    s.cut(0.0, "apple")
    assert s.tick(1.0) == 0
    s.cut(2.0, "kiwi")
    assert s.points == 2 and "combo" not in ev.types()


def test_three_in_a_swing_is_combo_with_bonus():
    s, ev, _ = make()
    for t in (0.0, 0.1, 0.2):
        s.cut(t, "orange")
    assert s.tick(0.3) == 0                  # gap not over yet
    assert s.tick(0.46) == 3
    assert s.points == 3 + 3 and s.best_combo == 3
    assert [e for e in ev.log if e["type"] == "combo"][0]["n"] == 3


def test_streak_events_and_double_points():
    s, ev, _ = make()
    for i in range(12):
        s.cut(i * 1.0, "lemon")
    streaks = [e["n"] for e in ev.log if e["type"] == "streak"]
    assert streaks == [5, 10]
    assert s.points == 9 + 2 * 3             # cuts 10, 11, 12 are doubled


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
