from game import config
from game.rules import Rules


def types(events):
    return [e["type"] for e in events]


def test_three_quick_cuts_make_a_combo_with_bonus():
    r = Rules()
    for i in range(3):
        r.on_cut("apple", 1, 1.0 + i * 0.1)
    events = r.update(1.2 + config.COMBO_GAP + 0.01)
    assert {"type": "combo", "n": 3} in events
    assert r.score == 3 + 3


def test_gap_ends_combo_even_if_cutting_continues():
    r = Rules()
    r.on_cut("apple", 1, 0.0)
    r.on_cut("apple", 1, 0.1)
    ev = r.on_cut("apple", 1, 0.1 + config.COMBO_GAP + 0.05)  # too late: new run
    assert "combo" not in types(ev)
    assert r.run == 1 and r.score == 3


def test_settle_pays_pending_combo():
    r = Rules()
    for i in range(4):
        r.on_cut("orange", 1, i * 0.05)
    assert types(r.settle()) == ["combo"]
    assert r.score == 8 and r.best_combo == 4


def test_streak_events_and_streak_broken():
    r = Rules()
    evs = []
    for i in range(5):
        evs += r.on_cut("apple", 1, i * 1.0)
    assert {"type": "streak", "n": 5} in evs
    drop = r.on_drop("apple", "left")
    assert types(drop) == ["miss", "streak_broken", "life_lost"]
    assert drop[0]["side"] == "left" and r.streak == 0


def test_lives_run_out():
    r = Rules()
    for _ in range(config.LIVES):
        last = r.on_drop("apple", "right")
    assert last[-1] == {"type": "life_lost", "lives_left": 0}
    assert r.over
    assert r.on_drop("apple", "right") == []  # nothing after game over
