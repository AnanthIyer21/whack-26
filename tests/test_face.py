"""Face extension: expression rules (synthetic), detector on real sample photos, and the thread end to end.

Photo tests download Google's MediaPipe sample portraits into tests/data/ (gitignored)
and are skipped when offline. No photo is ever committed.
"""

import os
import threading
import time
import urllib.request

import pytest

import shared
from face import config as C
from face.detector import Face, fist_over_face, player_face
from face.expressions import ExpressionTracker

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PHOTOS = {
    "portrait.jpg": "https://storage.googleapis.com/mediapipe-assets/portrait.jpg",          # broad open smile
    "business-person.jpg": "https://storage.googleapis.com/mediapipe-assets/business-person.png",  # slight smile
}

NEUTRAL = {"smile": 0.10, "jaw": 0.05, "brow": 0.10, "frown": 0.0}


def feed(tracker, start, seconds, sig, yaw=0.0, pitch=10.0):
    """Feed one held face for `seconds` at 10 Hz. Returns (end_time, list of fired (t, name))."""
    fired = []
    t = start
    end = start + seconds
    while t < end - 1e-9:
        current, f = tracker.update(t, sig, yaw, pitch)
        if f is not None:
            fired.append((round(t, 1), f[0]))
        t = round(t + 0.1, 3)
    return t, fired


def names(fired):
    out = []
    for t, name in fired:
        out.append(name)
    return out


def calibrated_tracker(sig=NEUTRAL, yaw=0.0, pitch=10.0):
    tr = ExpressionTracker()
    t, fired = feed(tr, 0.0, 6.0, sig, yaw, pitch)
    assert fired == []
    return tr, t


# ------------------------------------------------------------------ rules

def test_nothing_fires_during_warmup():
    tr = ExpressionTracker()
    t, fired = feed(tr, 0.0, 4.0, {"smile": 0.95, "jaw": 0.05, "brow": 0.1, "frown": 0.0})
    assert fired == []


def test_neutral_face_never_fires():
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 60.0, NEUTRAL)
    assert fired == []


def test_smile_fires_once_then_rearms():
    tr, t = calibrated_tracker()
    grin = {"smile": 0.9, "jaw": 0.05, "brow": 0.3, "frown": 0.0}
    t, fired = feed(tr, t, 3.0, grin)           # one long smile -> exactly one event
    assert names(fired) == ["smiling"]
    t, fired = feed(tr, t, 2.0, NEUTRAL)        # drops well below: re-armed
    assert fired == []
    t, fired = feed(tr, t, 2.0, grin)
    assert names(fired) == ["smiling"]


def test_naturally_smiley_face_needs_a_real_grin():
    resting = {"smile": 0.6, "jaw": 0.05, "brow": 0.1, "frown": 0.0}
    tr, t = calibrated_tracker(resting)
    t, fired = feed(tr, t, 3.0, {"smile": 0.75, "jaw": 0.05, "brow": 0.1, "frown": 0.0})
    assert fired == []
    t, fired = feed(tr, t, 3.0, {"smile": 0.97, "jaw": 0.05, "brow": 0.1, "frown": 0.0})
    assert names(fired) == ["smiling"]


def test_laughing_beats_smiling():
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 3.0, {"smile": 0.9, "jaw": 0.6, "brow": 0.3, "frown": 0.0})
    assert names(fired) == ["laughing"]


def test_smiley_face_talking_is_not_laughing():
    resting = {"smile": 0.6, "jaw": 0.05, "brow": 0.1, "frown": 0.0}
    tr, t = calibrated_tracker(resting)
    t, fired = feed(tr, t, 3.0, {"smile": 0.65, "jaw": 0.32, "brow": 0.1, "frown": 0.0})
    assert fired == []


def test_shock():
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 2.0, {"smile": 0.05, "jaw": 0.75, "brow": 0.1, "frown": 0.0})
    assert names(fired) == ["shock"]


def test_big_grin_is_not_frowning():
    """Measured on a real photo: a broad grin pushes browDown to ~0.8."""
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 3.0, {"smile": 0.95, "jaw": 0.12, "brow": 0.8, "frown": 0.0})
    assert "frowning" not in names(fired)


def test_frowning():
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 3.0, {"smile": 0.02, "jaw": 0.05, "brow": 0.75, "frown": 0.1})
    assert names(fired) == ["frowning"]


def test_looking_away_is_relative_to_usual_head_position():
    tr, t = calibrated_tracker(pitch=18.0)       # camera above the screen: "normal" reads 18 deg
    t, fired = feed(tr, t, 3.0, NEUTRAL, yaw=0.0, pitch=24.0)
    assert fired == []                           # only 6 deg from usual
    t, fired = feed(tr, t, 3.0, NEUTRAL, yaw=40.0, pitch=18.0)
    assert names(fired) == ["looking_away"]


def test_short_flicker_does_not_fire():
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 0.3, {"smile": 0.05, "jaw": 0.8, "brow": 0.1, "frown": 0.0})   # 0.3 s < 0.4 s hold
    t, fired2 = feed(tr, t, 2.0, NEUTRAL)
    assert fired == [] and fired2 == []


def test_interruptions_restart_the_hold():
    tr, t = calibrated_tracker()
    grin = {"smile": 0.9, "jaw": 0.05, "brow": 0.3, "frown": 0.0}
    fired = []
    for i in range(10):                          # fist crosses the face every 0.3 s
        t, f = feed(tr, t, 0.3, grin)
        fired.extend(f)
        tr.interrupt()
    assert fired == []


def test_disabled_expression_never_fires(monkeypatch):
    monkeypatch.setattr(C, "ENABLED_EXPRESSIONS", ("laughing", "shock", "frowning", "looking_away"))
    tr, t = calibrated_tracker()
    t, fired = feed(tr, t, 3.0, {"smile": 0.9, "jaw": 0.05, "brow": 0.3, "frown": 0.0})
    assert fired == []


def test_player_is_the_largest_face_and_ambiguity_means_none():
    big = Face((0.4, 0.1, 0.6, 0.4), 1000.0, NEUTRAL, 0, 0)
    small = Face((0.1, 0.1, 0.2, 0.2), 300.0, NEUTRAL, 0, 0)
    similar = Face((0.7, 0.1, 0.9, 0.4), 900.0, NEUTRAL, 0, 0)
    assert player_face([big, small]) is big
    assert player_face([big, similar]) is None
    assert player_face([]) is None


def test_fist_over_face():
    box = (0.4, 0.1, 0.6, 0.4)
    over = shared.HandState(sword_visible=True, blade_base=(0.5, 0.3))
    near = shared.HandState(sword_visible=True, blade_base=(0.62, 0.3))     # inside the +15% margin
    away = shared.HandState(sword_visible=True, blade_base=(0.9, 0.8))
    hidden = shared.HandState(sword_visible=False, blade_base=(0.5, 0.3))
    assert fist_over_face(box, over)
    assert fist_over_face(box, near)
    assert not fist_over_face(box, away)
    assert not fist_over_face(box, hidden)


def test_face_event_builder():
    e = shared.ev_face("laughing", 0.678)
    assert e["type"] == shared.FACE and e["expression"] == "laughing" and e["strength"] == 0.68
    with pytest.raises(ValueError):
        shared.ev_face("sneezing", 1.0)


# ------------------------------------------------------------- real photos

def photo(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        os.makedirs(DATA, exist_ok=True)
        try:
            urllib.request.urlretrieve(PHOTOS[name], path + ".part")
        except Exception:
            pytest.skip("offline: can't download the MediaPipe sample photo")
        import cv2
        img = cv2.imread(path + ".part")
        os.remove(path + ".part")
        if img is None:
            pytest.skip("sample photo unreadable")
        if img.shape[1] > 480:
            img = cv2.resize(img, (480, int(img.shape[0] * 480 / img.shape[1])))
        cv2.imwrite(path, img)
    import cv2
    return cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)


@pytest.fixture(scope="module")
def detector():
    from face.detector import FaceDetector
    d = FaceDetector(mode="image")
    yield d
    d.close()


def test_photo_broad_smile_reads_as_smiling(detector):
    faces = detector.detect(photo("portrait.jpg"))
    assert len(faces) == 1
    f = player_face(faces)
    assert f.signals["smile"] > 0.8
    assert abs(f.yaw) < 15
    assert detector.last_ms < 100


def test_photo_slight_smile_is_much_lower(detector):
    f = player_face(detector.detect(photo("business-person.jpg")))
    assert 0.3 < f.signals["smile"] < 0.8
    assert f.signals["jaw"] < 0.2


def test_face_thread_end_to_end():
    """Real face model, real thread: a slight-smile face for 6 s (calibration), then a broad grin -> 'smiling'."""
    import face
    calm = photo("business-person.jpg")
    grin = photo("portrait.jpg")
    while not shared.events.empty():
        shared.events.get_nowait()
    stop = threading.Event()
    thread = threading.Thread(target=face.run, args=(stop,), daemon=True)
    thread.start()
    posted = []
    started = time.monotonic()
    try:
        while time.monotonic() - started < 9.0:
            elapsed = time.monotonic() - started
            shared.set_latest_frame((calm if elapsed < 6.5 else grin).copy(), time.monotonic())
            time.sleep(1 / 30.0)
            while not shared.events.empty():
                posted.append(shared.events.get_nowait())
    finally:
        stop.set()
        thread.join(3.0)
        shared.set_latest_frame(None, 0.0)
    assert not thread.is_alive()
    expressions = []
    for e in posted:
        if e["type"] == shared.FACE:
            expressions.append(e["expression"])
    assert expressions == ["smiling"]
    assert face.diag["ms"] < 100
