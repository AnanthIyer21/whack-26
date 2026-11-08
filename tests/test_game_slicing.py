import math

from game import config as C
from game.blade import Blade
from game.geometry import circle_hits_quad, wrap_angle
from game.input import HandSample
from game.spawner import Spawner


def sample(x, y, a, t, grip=True, hands=1):
    return HandSample((x, y), a, grip, hands, t)


def drawn_blade():
    b = Blade(0.30)
    b.draw_out(0.0)
    b.update(sample(640, 400, -math.pi / 2, 0.0), 1.0)  # past DRAW_TIME -> drawn
    b.take_sweeps()
    return b


def test_circle_quad_basic():
    quad = [(0, 0), (100, 0), (100, 10), (0, 10)]
    assert circle_hits_quad(50, 5, 1, quad)          # inside
    assert circle_hits_quad(50, 20, 12, quad)        # touches edge
    assert not circle_hits_quad(50, 40, 12, quad)    # clear


def test_degenerate_quad_is_a_line():
    line = [(0, 0), (100, 0), (100, 0), (0, 0)]
    assert circle_hits_quad(50, 5, 6, line)
    assert not circle_hits_quad(50, 20, 6, line)


def test_fast_horizontal_swipe_cuts_fruit_between_frames():
    b = drawn_blade()
    # blade moves 300 px right in one 1/30 s vision frame: fruit in the gap must be hit
    b.update(sample(940, 400, -math.pi / 2, 1 / 30), 1.04)
    sweeps = b.take_sweeps()
    assert sweeps and sweeps[0].speed > C.CUT_SPEED
    assert any(circle_hits_quad(790, 300, 20, s.quad) for s in sweeps)


def test_large_rotation_is_substepped_and_covers_arc():
    b = drawn_blade()
    # rotate 120 degrees around a fixed fist: up -> pointing down-right
    b.update(sample(640, 400, -math.pi / 2 + math.radians(120), 1 / 30), 1.04)
    sweeps = b.take_sweeps()
    assert len(sweeps) >= 8
    L = 0.30 * C.H
    # a fruit near the arc at 30 degrees (beyond the straight chord) must be covered
    a = -math.pi / 2 + math.radians(60)
    fx, fy = 640 + math.cos(a) * L * 0.98, 400 + math.sin(a) * L * 0.98
    assert any(circle_hits_quad(fx, fy, 5, s.quad) for s in sweeps)


def test_long_gap_never_cuts():
    b = drawn_blade()
    b.update(sample(1200, 400, -math.pi / 2, 1.2), 2.2)   # 1.2 s gap: the hand was really gone
    assert b.take_sweeps() == []


def test_reset_needs_two_fresh_samples():
    b = drawn_blade()
    b.reset_history()                                    # e.g. after a pause or input switch
    b.update(sample(1000, 400, -math.pi / 2, 0.1), 1.1)  # first sample after reset
    assert b.take_sweeps() == []
    b.update(sample(1100, 400, -math.pi / 2, 0.1 + 1 / 30), 1.13)
    assert b.take_sweeps()


def test_lag_spike_is_bridged_and_cuts_fruit_in_the_path():
    b = drawn_blade()
    b.update(sample(700, 400, -math.pi / 2, 1 / 30), 1.03)          # swinging right, fast
    b.take_sweeps()
    b.update(sample(1100, 400, -math.pi / 2, 1 / 30 + 0.3), 1.33)   # 0.3 s lag, then 400 px on
    sweeps = b.take_sweeps()
    assert sweeps and all(sw.bridged for sw in sweeps)
    assert sweeps[0].speed >= C.CUT_SPEED                            # kept the swing speed
    assert any(circle_hits_quad(900, 300, 20, sw.quad) for sw in sweeps)   # fruit mid-lag: cut


def test_short_dropout_is_bridged_from_the_last_good_spot():
    b = drawn_blade()
    b.update(sample(700, 400, -math.pi / 2, 1 / 30), 1.03)
    b.take_sweeps()
    b.freeze()                                           # hand lost for a moment
    b.unfreeze()
    b.update(sample(1000, 400, -math.pi / 2, 0.3), 1.3)  # back 0.27 s later, further along
    sweeps = b.take_sweeps()
    assert any(circle_hits_quad(850, 300, 20, sw.quad) for sw in sweeps)


def test_too_long_or_teleport_is_never_bridged():
    b = drawn_blade()
    b.update(sample(700, 400, -math.pi / 2, 1 / 30), 1.03)
    b.take_sweeps()
    b.update(sample(1000, 400, -math.pi / 2, 1.2), 2.2)    # 1.17 s: genuinely lost
    assert b.take_sweeps() == []
    b2 = drawn_blade()
    b2.update(sample(660, 400, -math.pi / 2, 1 / 30), 1.03)
    b2.take_sweeps()
    b2.update(sample(-700, 400, -math.pi / 2, 0.2), 1.2)   # jumped > 0.95 of the width: glitch
    assert b2.take_sweeps() == []


def test_pause_never_bridges():
    b = drawn_blade()
    b.sheathe()                                          # paused
    b.draw_out(2.0)                                      # resumed
    b.update(sample(1200, 400, -math.pi / 2, 0.2), 2.5)
    b.update(sample(1210, 400, -math.pi / 2, 0.2 + 1 / 30), 2.53)
    assert all(not circle_hits_quad(900, 300, 20, sw.quad) for sw in b.take_sweeps())


def test_no_cut_while_drawing():
    b = Blade(0.30)
    b.draw_out(0.0)
    b.update(sample(640, 400, -math.pi / 2, 0.0), 0.01)
    b.update(sample(940, 400, -math.pi / 2, 1 / 30), 0.04)
    assert b.take_sweeps() == []


def test_wrap_angle():
    assert abs(wrap_angle(3 * math.pi / 2) + math.pi / 2) < 1e-9


def test_spawner_no_bombs_first_5s_and_ramps():
    sp = Spawner()
    gap0, nmin0, nmax0, bomb0, _, _ = sp.params(0, 60)
    gap1, nmin1, nmax1, bomb1, _, _ = sp.params(60, 60)
    assert bomb0 == 0 and nmax0 == 1 and abs(gap0 - 1.3) < 1e-9
    assert nmin1 == 3 and nmax1 == 5 and bomb1 > 0.19 and gap1 < 0.7
