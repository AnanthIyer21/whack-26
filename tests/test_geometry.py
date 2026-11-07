import math

import numpy as np
import pytest

from tests.synthetic import ROT_X, detected, fist, half_curl, open_hand
from vision import config, geometry


def rot_z(deg):
    r = math.radians(deg)
    return np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])


def rot_y(deg):
    r = math.radians(deg)
    return np.array([[math.cos(r), 0, math.sin(r)], [0, 1, 0], [-math.sin(r), 0, math.cos(r)]])


ROTATIONS = [None, rot_z(45), rot_z(-90), rot_z(180), rot_y(70), ROT_X(60), rot_y(80) @ rot_z(30)]


@pytest.mark.parametrize("rot", ROTATIONS)
def test_fist_is_grip_at_any_rotation(rot):
    score, curls, n = geometry.curl_score(fist(rotation=rot))
    assert score >= 0.8, curls
    assert n == 4
    assert geometry.raw_grip(score, n)


@pytest.mark.parametrize("rot", ROTATIONS)
def test_open_hand_is_open_at_any_rotation(rot):
    score, curls, n = geometry.curl_score(open_hand(rotation=rot))
    assert score <= config.OPEN_BELOW, curls
    assert not geometry.raw_grip(score, n)


def test_half_curl_is_in_between():
    score, _, _ = geometry.curl_score(half_curl())
    assert config.OPEN_BELOW < score < 0.8


def test_mirroring_does_not_change_curl():
    w = fist()
    mirrored = w * np.array([-1, 1, 1])
    assert geometry.curl_score(w)[0] == pytest.approx(geometry.curl_score(mirrored)[0], abs=1e-5)


def test_normalise():
    w = open_hand() + np.array([0.3, 0.2, 0.1])
    n = geometry.normalise(w, "Right")
    assert np.allclose(n[0], 0)
    assert np.linalg.norm(n[9]) == pytest.approx(1.0, abs=1e-5)
    nl = geometry.normalise(w, "Left")
    assert np.allclose(nl[:, 0], -n[:, 0])


def test_knuckle_mode_upright_fist_points_up():
    h = detected(fist())
    a = geometry.blade_angle(h.img, 640, 480, mode="knuckle")
    assert a == pytest.approx(-math.pi / 2, abs=0.05)


def test_grip_mode_blade_runs_across_the_fist_out_of_the_thumb_side():
    # Synthetic right hand, palm up: index knuckle is at -x (thumb side), pinky at +x.
    h = detected(fist())
    a = geometry.blade_angle(h.img, 640, 480, mode="grip")
    assert abs(abs(a) - math.pi) < 0.25          # horizontal, pointing towards the thumb side (-x)
    # Mirror it into a left hand: blade must still exit the thumb side (now +x).
    left = detected(fist() * np.array([-1, 1, 1]), label="Left")
    assert abs(geometry.blade_angle(left.img, 640, 480, mode="grip")) < 0.25


def test_grip_base_is_inside_the_fist():
    h = detected(fist(), x=0.3, y=0.7)
    base = geometry.blade_base(h.img, mode="grip")
    knuckles = h.img[[5, 9, 13, 17], :2].mean(axis=0)
    palm = np.linalg.norm(h.img[9, :2] - h.img[0, :2])
    # The grip centre sits in the fist, right by the knuckle line (not out past the fingers).
    assert np.linalg.norm(base - knuckles) < 0.3 * palm
    xs = h.img[[5, 17], 0]
    assert xs.min() <= base[0] <= xs.max()     # between the index and pinky sides


def test_blade_angle_uses_pixel_proportions():
    img = np.zeros((21, 3), np.float32)
    img[0, :2] = (0.5, 0.5)
    img[9, :2] = (0.6, 0.6)   # equal in normalised units, but 640 wide vs 480 tall
    a = geometry.blade_angle(img, 640, 480, mode="knuckle")
    assert a == pytest.approx(math.atan2(0.1 * 480, 0.1 * 640))


def test_knuckle_mode_base_is_knuckle_centroid():
    h = detected(open_hand(), x=0.3, y=0.7)
    assert np.allclose(geometry.blade_base(h.img, mode="knuckle"), h.img[[5, 9, 13, 17], :2].mean(axis=0))


def test_foreshortening_knuckle_mode():
    assert geometry.foreshortening(open_hand(), mode="knuckle") == pytest.approx(1.0, abs=0.01)
    pointing_at_camera = open_hand(rotation=ROT_X(80))
    assert geometry.foreshortening(pointing_at_camera, mode="knuckle") < config.SIDE_ON_RATIO


def test_foreshortening_grip_mode():
    assert geometry.foreshortening(fist(), mode="grip") > 0.8
    thumb_at_camera = fist(rotation=rot_y(80))   # blade axis now points into the camera
    assert geometry.foreshortening(thumb_at_camera, mode="grip") < config.SIDE_ON_RATIO


def test_grip_certainty():
    assert geometry.grip_certainty(1.0) == 1.0
    assert geometry.grip_certainty(0.0) == 1.0
    assert geometry.grip_certainty((config.GRIP_ENTER + config.OPEN_BELOW) / 2) == 0.0


def test_curl_maths_is_fast():
    import time
    w = fist()
    t0 = time.perf_counter()
    for _ in range(1000):
        geometry.curl_score(w)
    per_call_ms = (time.perf_counter() - t0)
    assert per_call_ms < 0.5, f"{per_call_ms:.3f} ms per call"
