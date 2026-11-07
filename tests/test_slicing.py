import math

from game.slicing import swept_hit

UP = -math.pi / 2
L = 200


def test_horizontal_swing_through_fruit_hits():
    # blade pointing up, base moves from x=0 to x=200 at y=400; fruit at (100, 300)
    assert swept_hit((0, 400), UP, (200, 400), UP, L, (100, 300), 30)


def test_swing_that_stops_short_misses():
    assert not swept_hit((0, 400), UP, (40, 400), UP, L, (100, 300), 30)


def test_huge_fast_jump_still_hits_fruit_in_between():
    assert swept_hit((0, 400), UP, (1200, 400), UP, L, (600, 250), 20)


def test_fruit_beyond_blade_tip_misses():
    assert not swept_hit((0, 400), UP, (200, 400), UP, L, (100, 100), 30)


def test_pure_rotation_sweeps_an_arc():
    # base still, blade rotates from pointing right to pointing up: fruit at 45 degrees
    fruit = (500 + 150 * math.cos(-math.pi / 4), 400 + 150 * math.sin(-math.pi / 4))
    assert swept_hit((500, 400), 0.0, (500, 400), UP, L, fruit, 20)


def test_no_movement_only_touches_fruit_on_the_blade():
    assert swept_hit((0, 400), UP, (0, 400), UP, L, (0, 300), 10)
    assert not swept_hit((0, 400), UP, (0, 400), UP, L, (100, 300), 10)
