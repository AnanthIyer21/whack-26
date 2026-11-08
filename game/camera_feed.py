"""Camera-only feed for MOUSE MODE, so the webcam is the background even without vision.

Team rule: only vision opens the camera. In mouse mode the vision thread isn't started, so
nothing else holds the camera; this thread opens it, publishes mirrored RGB frames with
shared.set_latest_frame() (exactly what vision would), and never touches HandState.
It is never started alongside real or fake vision. If there's no camera (or no permission),
it gives up quietly and the game shows the normal background.
"""
import threading
import time

import shared

HZ = 30


def _run(stop_event, index, width, height):
    try:
        import cv2
    except ImportError:
        print("[game camera] OpenCV not installed: no webcam background")
        return
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION) if hasattr(cv2, "CAP_AVFOUNDATION") else cv2.VideoCapture(index)
    if not cap.isOpened():
        print("[game camera] couldn't open the camera (in use, or no permission): no webcam background")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    print("[game camera] webcam background on (mouse mode)")
    period = 1.0 / HZ
    try:
        while not stop_event.is_set():
            t0 = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                stop_event.wait(0.05)
                continue
            frame = cv2.flip(frame, 1)                       # selfie mirror, like vision
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            shared.set_latest_frame(rgb, time.monotonic())
            stop_event.wait(max(0.0, period - (time.monotonic() - t0)))
    finally:
        cap.release()
        shared.set_latest_frame(None, 0.0)


def start(stop_event, index=0, width=1280, height=720):
    t = threading.Thread(target=_run, args=(stop_event, index, width, height), name="game-camera", daemon=True)
    t.start()
    return t
