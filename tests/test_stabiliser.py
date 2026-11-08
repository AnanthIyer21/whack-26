import math

import numpy as np
import pytest

from tests.synthetic import detected, fist, open_hand
from vision import config
from vision.one_euro import AngleFilter, OneEuroFilter
from vision.stabiliser import GRIP, OPEN, UNCLEAR, BladeSmoother, GripStabiliser, HandCounter

DT = 1 / 30


# ---------- GripStabiliser ----------

def feed(stab, scores, n=4):
    return [stab.update(s, n) for s in scores]


def test_grip_needs_two_frames():
    s = GripStabiliser()
    assert feed(s, [0.9]) == [UNCLEAR] or feed(GripStabiliser(), [0.9])[0] != GRIP
    s = GripStabiliser()
    assert feed(s, [0.9, 0.9]) == [UNCLEAR, GRIP]


def test_grip_needs_enough_fingers():
    s = GripStabiliser()
    assert GRIP not in [s.update(0.9, 2) for _ in range(5)]


def test_no_flicker_at_boundary():
    s = GripStabiliser()
    feed(s, [0.9, 0.9])
    # Noise around the boundary: dips to 0.35 for 2 frames at a time never drops GRIP.
    states = feed(s, [0.5, 0.35, 0.35, 0.55, 0.35, 0.38, 0.62, 0.45] * 5)
    assert set(states) == {GRIP}


def test_leaves_grip_after_three_low_frames():
    s = GripStabiliser()
    feed(s, [0.9, 0.9])
    assert feed(s, [0.1, 0.1, 0.1]) == [GRIP, GRIP, OPEN]


def test_open_vs_unclear():
    s = GripStabiliser()
    assert s.update(0.1, 0) == OPEN
    assert s.update(0.45, 1) == UNCLEAR


# ---------- HandCounter ----------

def test_grace_holds_then_drops():
    c = HandCounter()
    h = detected(fist())
    t = 0.0
    assert c.update([h], t)[:2] == (h, 1)
    t += DT
    hand, count, held = c.update([], t)
    assert hand is h and count == 1 and held
    t += config.LOST_GRACE_S  # now past the grace window
    hand, count, held = c.update([], t)
    assert hand is None and count == 0 and not held and c.lost


def test_two_hands_debounced_both_ways():
    c = HandCounter()
    a, b = detected(fist(), x=0.3), detected(open_hand(), x=0.7)
    t = 0.0
    counts = []
    for hands in [[a], [a, b], [a], [a, b], [a, b], [a, b], [a, b], [a], [a, b], [a], [a], [a]]:
        counts.append(c.update(hands, t)[1]); t += DT
    assert counts == [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 1]


def test_sword_hand_stays_with_the_original_hand():
    c = HandCounter()
    a = detected(fist(), x=0.3, score=0.7)
    b = detected(open_hand(), x=0.7, score=0.99)   # more confident, but not the sword hand
    c.update([a], 0.0)
    for i in range(5):
        a_moved = detected(fist(), x=0.3 + 0.01 * i, score=0.7)
        sword, _, _ = c.update([b, a_moved], DT * (i + 1))
        assert sword is a_moved


# ---------- One Euro ----------

def test_one_euro_smooths_jitter_at_rest():
    f = OneEuroFilter(config.POS_MIN_CUTOFF, config.POS_BETA)
    rng = np.random.default_rng(0)
    out = [f(0.5 + rng.normal(0, 0.005, 2), i * DT) for i in range(200)]
    assert np.std(np.array(out[50:]), axis=0).max() < 0.002


def test_one_euro_follows_fast_motion():
    f = OneEuroFilter(config.POS_MIN_CUTOFF, config.POS_BETA)
    # Swing at 3 screen-widths per second for 0.3 s.
    xs = [np.array([0.1 + 3 * i * DT, 0.5]) for i in range(10)]
    out = [f(x, i * DT) for i, x in enumerate(xs)]
    lag = xs[-1][0] - out[-1][0]
    assert lag < 0.12, lag   # under ~1.3 frames of motion behind


def test_angle_filter_no_wrap_jump():
    f = AngleFilter(config.ANG_MIN_CUTOFF, config.ANG_BETA)
    out = [f(math.pi - 0.01 if i % 2 else -math.pi + 0.01, i * DT) for i in range(60)]
    # Raw input flips sign every frame across +-pi; output must stay near +-pi, never near 0.
    assert all(abs(abs(a) - math.pi) < 0.05 for a in out)


# ---------- BladeSmoother side-on hold ----------

def test_side_on_holds_angle_then_blends_back():
    b = BladeSmoother()
    t = 0.0
    for _ in range(30):
        b.update((0.5, 0.5), -math.pi / 2, 1.0, t); t += DT
    # Fist points at the camera: raw angle goes wild, output must hold.
    for raw in [0.3, 2.5, -1.0, 1.7, 0.0]:
        _, a = b.update((0.5, 0.5), raw, 0.2, t); t += DT
        assert a == pytest.approx(-math.pi / 2, abs=0.05)
        assert b.side_on
    # Visible again at a new angle: converges without a jump.
    prev = a
    for _ in range(30):
        _, a = b.update((0.5, 0.5), 0.0, 1.0, t); t += DT
        assert abs(a - prev) < 0.6
        prev = a
    assert a == pytest.approx(0.0, abs=0.05)
