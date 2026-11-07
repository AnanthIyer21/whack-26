"""Step-1 smoke test: camera fps, MediaPipe speed, and the handedness check.

Run:  .venv\\Scripts\\python -m tools.camera_check
Hold up your RIGHT hand: the label should say Right. Then your left. Q to quit.
"""
import time

import cv2
import numpy as np

from vision.capture import Camera
from vision.tracker import HAND_CONNECTIONS, HandTracker


def main():
    cam = Camera().open()
    print("camera:", cam.info())
    tracker = HandTracker()
    frame_times, mp_ms = [], []
    t_prev = time.monotonic()
    while True:
        bgr = cam.read_bgr()
        if bgr is None:
            print("frame read failed"); break
        t = time.monotonic()
        frame_times.append(t - t_prev); t_prev = t
        rgb = Camera.to_rgb_mirrored(bgr)
        t0 = time.perf_counter()
        hands = tracker.detect(rgb, t)
        mp_ms.append((time.perf_counter() - t0) * 1000)

        view = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        h, w = view.shape[:2]
        for hand in hands:
            pts = (hand.img[:, :2] * (w, h)).astype(int)
            for a, b in HAND_CONNECTIONS:
                cv2.line(view, tuple(pts[a]), tuple(pts[b]), (0, 255, 0), 2)
            for p in pts:
                cv2.circle(view, tuple(p), 3, (0, 0, 255), -1)
            cv2.putText(view, f"{hand.label} {hand.score:.2f}", tuple(pts[0] + (10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        recent = frame_times[-30:]
        fps = len(recent) / max(sum(recent), 1e-6)
        cv2.putText(view, f"cam {fps:4.1f} fps  mediapipe {np.mean(mp_ms[-30:]):5.1f} ms  hands {len(hands)}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow("camera_check (Q to quit)", view)
        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            break
    cam.close(); tracker.close(); cv2.destroyAllWindows()
    ft = np.array(frame_times[10:]) if len(frame_times) > 20 else np.array(frame_times)
    mp = np.array(mp_ms[10:]) if len(mp_ms) > 20 else np.array(mp_ms)
    if len(ft):
        print(f"camera fps: mean {1 / ft.mean():.1f}")
        print(f"mediapipe ms: mean {mp.mean():.1f}  p95 {np.percentile(mp, 95):.1f}  max {mp.max():.1f}")


if __name__ == "__main__":
    main()
