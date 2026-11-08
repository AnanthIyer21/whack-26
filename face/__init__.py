"""Face extension: GRIP-9000 reads your expressions live. Owner: Ananth. Only runs with --face.

main.py calls face.run(stop_event) on a daemon thread. It never opens the camera:
it reads vision's latest frame (shared.get_latest_frame), publishes a FaceState and
posts a 'face' event to shared.events when the player holds an expression.
Expressions only: no identity, no images stored.
"""

import time
import traceback

import shared
from face import config as C

# Live numbers for main.py --diag and tools/face_debug.py (read-only for others).
diag = {"ms": 0.0, "fps": 0.0, "faces": 0, "state": "starting", "levels": {}}


def run(stop_event):
    from face.detector import FaceDetector, fist_over_face, player_face
    from face.expressions import ExpressionTracker

    try:
        detector = FaceDetector(mode="video")
    except Exception as exc:
        print("[face] could not start the face model: " + repr(exc) + " (face reactions off)")
        diag["state"] = "off (model failed)"
        return

    tracker = ExpressionTracker()
    period = 1.0 / C.RATE_HZ
    last_frame_t = None
    last_seen_t = None          # last time we had (or plausibly had) the player's face
    last_box = None
    frames = 0
    fps_started = time.monotonic()
    print("[face] reading expressions at " + str(C.RATE_HZ) + " Hz")
    try:
        while not stop_event.is_set():
            loop_started = time.monotonic()
            frame, frame_t = shared.get_latest_frame()
            if frame is None or frame_t == last_frame_t:
                stop_event.wait(0.02)
                continue
            last_frame_t = frame_t
            try:
                last_box, last_seen_t = _step(detector, tracker, frame, frame_t, last_box, last_seen_t,
                                              player_face, fist_over_face)
            except Exception:
                traceback.print_exc()           # one bad frame must never kill the face thread
            frames += 1
            now = time.monotonic()
            if now - fps_started >= 1.0:
                diag["fps"] = frames / (now - fps_started)
                frames = 0
                fps_started = now
            stop_event.wait(max(0.0, period - (time.monotonic() - loop_started)))
    finally:
        shared.set_face_state(shared.FaceState(t=time.monotonic()))
        detector.close()


def _step(detector, tracker, frame, t, last_box, last_seen_t, player_face, fist_over_face):
    faces = detector.detect(frame, t)
    diag["ms"] = detector.last_ms
    diag["faces"] = len(faces)
    hand = shared.get_hand_state()
    face = player_face(faces)

    if face is None:
        covered = last_box is not None and fist_over_face(last_box, hand)
        if faces or covered:
            # Ambiguous (two similar faces) or the fist is covering the face: unreadable, not lost.
            tracker.interrupt()
            diag["state"] = "covered" if covered else "ambiguous"
            _publish(tracker, t, False, len(faces))
            return last_box, t
        if last_seen_t is not None and t - last_seen_t > C.FACE_LOST_RESET:
            tracker.reset()                     # face gone a while: likely a new player
            last_box = None
        else:
            tracker.interrupt()
        diag["state"] = "no face"
        _publish(tracker, t, False, 0)
        return last_box, last_seen_t

    if fist_over_face(face.box, hand):
        tracker.interrupt()
        diag["state"] = "covered"
        _publish(tracker, t, False, len(faces))
        return face.box, t

    current, fired = tracker.update(t, face.signals, face.yaw, face.pitch)
    diag["state"] = current if tracker.calibrated(t) else "calibrating"
    diag["levels"] = dict(tracker.last_levels)
    _publish(tracker, t, True, len(faces), face.signals)
    if fired is not None:
        shared.post_event(shared.ev_face(fired[0], fired[1]))
    return face.box, t


def _publish(tracker, t, visible, count, raw=None):
    scores = {}
    if tracker.smoothed is not None:
        for name in ("smile", "jaw", "brow", "frown"):
            scores[name] = round(tracker.smoothed[name], 3)
    shared.set_face_state(shared.FaceState(
        face_visible=visible,
        expression=tracker.current if visible else "neutral",
        scores=scores,
        yaw=round(tracker.last_yaw, 1),
        pitch=round(tracker.last_pitch, 1),
        faces_in_view=count,
        calibrated=tracker.calibrated(t),
        t=t,
    ))
