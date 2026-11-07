import math

import numpy as np

from tests.synthetic import detected, fist, open_hand
from vision import config
from vision.fakes import HandState
from vision.pipeline import VisionPipeline

DT = 1 / 30


class FakeTracker:
    """Plays back a script of hand lists, one per frame."""

    def __init__(self, script):
        self.script = list(script)

    def detect(self, rgb, t):
        return self.script.pop(0) if self.script else []

    def close(self):
        pass


def run(script):
    p = VisionPipeline(640, 480, tracker=FakeTracker(script))
    frame = np.zeros((480, 640, 3), np.uint8)
    out = []
    for i in range(len(script)):
        fields, _ = p.process(frame, i * DT)
        HandState(**fields)          # fields must match HandState exactly
        out.append(fields)
    return out


def test_fist_activates_sword_open_deactivates():
    f, o = detected(fist()), detected(open_hand())
    out = run([[f]] * 4 + [[o]] * 4)
    active = [s["sword_active"] for s in out]
    assert active == [False, True, True, True, True, True, False, False]
    assert all(s["hands_in_frame"] == 1 and s["sword_visible"] for s in out)


def test_two_hands_forces_sword_off():
    a, b = detected(fist(), x=0.3), detected(open_hand(), x=0.7)
    out = run([[a]] * 3 + [[a, b]] * 4 + [[a]] * 4)
    assert [s["hands_in_frame"] for s in out] == [1, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1]
    assert [s["sword_active"] for s in out] == [False, True, True, True, True, False, False,
                                                 False, False, True, True]


def test_dropout_grace_keeps_playing_then_reports_no_hand():
    f = detected(fist())
    gap = int(config.LOST_GRACE_S / DT)          # frames inside the grace window
    out = run([[f]] * 3 + [[]] * (gap + 2))
    inside = out[3:3 + gap]
    assert all(s["sword_active"] and s["hands_in_frame"] == 1 for s in inside)
    assert out[-1]["hands_in_frame"] == 0 and not out[-1]["sword_visible"]
    assert out[-1]["confidence"] == 0.0


def test_blade_points_up_for_upright_fist_in_knuckle_mode(monkeypatch):
    monkeypatch.setattr(config, "BLADE_MODE", "knuckle")
    out = run([[detected(fist(), x=0.4, y=0.6)]] * 10)
    assert math.isclose(out[-1]["blade_angle"], -math.pi / 2, abs_tol=0.05)
    bx, by = out[-1]["blade_base"]
    assert 0.3 < bx < 0.5 and 0.4 < by < 0.6
