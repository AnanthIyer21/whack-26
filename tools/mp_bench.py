"""Which MediaPipe setup is fastest on this laptop, with a real hand in view?

Run:  .venv\\Scripts\\python -m tools.mp_bench
Hold ONE fist up in view the whole time, moving it gently (~40 s).
Cycles through setups, twice each, and prints mean / p95 ms per setup.
Does not change any camera settings. No window (headless OpenCV): Ctrl+C aborts.
"""
import time

import cv2
import numpy as np

from vision.capture import Camera
from vision.tracker import HandTracker

SETUPS = [  # (name, num_hands, input scale)
    ("2 hands, 640x480", 2, 1.0),
    ("1 hand,  640x480", 1, 1.0),
    ("2 hands, 320x240", 2, 0.5),
    ("1 hand,  320x240", 1, 0.5),
]
SECONDS_EACH = 5
ROUNDS = 2


def main():
    cam = Camera().open()
    trackers = {n: HandTracker(max_hands=n) for n in (1, 2)}
    results = {name: {"ms": [], "frames": 0, "found": 0} for name, _, _ in SETUPS}
    try:
        for rnd in range(ROUNDS):
            for name, n, scale in SETUPS:
                tr = trackers[n]
                print(f"round {rnd + 1}: {name} ... keep your fist in view", flush=True)
                t_end = time.monotonic() + SECONDS_EACH
                warm = 5   # skip the first frames after switching
                while time.monotonic() < t_end:
                    bgr = cam.read_bgr()
                    t = time.monotonic()
                    rgb = Camera.to_rgb_mirrored(bgr)
                    if scale != 1.0:
                        rgb = np.ascontiguousarray(cv2.resize(rgb, None, fx=scale, fy=scale,
                                                              interpolation=cv2.INTER_AREA))
                    p0 = time.perf_counter()
                    hands = tr.detect(rgb, t)
                    ms = (time.perf_counter() - p0) * 1e3
                    if warm > 0:
                        warm -= 1
                    else:
                        r = results[name]
                        r["frames"] += 1
                        if hands:
                            r["found"] += 1
                            r["ms"].append(ms)
    except KeyboardInterrupt:
        print("aborted early; partial results:")
    finally:
        cam.close()
        for tr in trackers.values():
            tr.close()

    print("\nsetup               mediapipe mean   p95    hand found")
    for name, _, _ in SETUPS:
        r = results[name]
        if r["ms"]:
            a = np.array(r["ms"])
            print(f"{name:<18}  {a.mean():9.1f} ms {np.percentile(a, 95):6.1f} ms   "
                  f"{100 * r['found'] / max(r['frames'], 1):5.1f}%")
        else:
            print(f"{name:<18}  no hand seen")


if __name__ == "__main__":
    main()
