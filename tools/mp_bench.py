"""Which MediaPipe setup is fastest on this laptop, with a real hand in view?

Run:  .venv\\Scripts\\python -m tools.mp_bench
Hold ONE fist up in view the whole time, moving it gently (~40 s).
Cycles through setups, twice each, and prints mean / p95 ms per setup.
Does not change any camera settings.
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
    win = "mp_bench: hold ONE fist in view (Q aborts)"
    try:
        for rnd in range(ROUNDS):
            for name, n, scale in SETUPS:
                tr = trackers[n]
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
                    view = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), (320, 240))
                    cv2.putText(view, f"{name}  round {rnd + 1}", (6, 20), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 255), 1)
                    cv2.putText(view, f"{ms:5.1f} ms  hand {'YES' if hands else 'no'}", (6, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if hands else (0, 0, 255), 1)
                    cv2.imshow(win, view)
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("aborted early; partial results:")
    finally:
        cam.close()
        for tr in trackers.values():
            tr.close()
        cv2.destroyAllWindows()

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
