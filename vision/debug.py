"""Vision debug window.

Run:  .venv\\Scripts\\python -m vision.debug  [--camera 1]

Shows the mirrored camera with every hand's skeleton, the sword hand coloured
by grip state, the raw (thin) and smoothed (thick) blade, per-finger curl bars,
hands_in_frame, the HandState being published, fps and ms per stage.
A second window has sliders for live tuning.

Keys:  Q quit   P print current tunables (paste them into vision/config.py)
       C counter mode (reliability check, coming in step 6)
"""
import argparse
import math
import threading
from collections import deque

import cv2
import numpy as np

from vision import config, start
from vision.fakes import FakeShared
from vision.geometry import FINGER_NAMES
from vision.stabiliser import GRIP, OPEN, UNCLEAR
from vision.tracker import HAND_CONNECTIONS

PANEL_W = 330
BLADE_LEN_PX = 170          # debug-only; the game uses shared/'s blade length
COLOURS = {GRIP: (60, 220, 60), OPEN: (60, 60, 230), UNCLEAR: (0, 200, 230), None: (160, 160, 160)}
FONT = cv2.FONT_HERSHEY_SIMPLEX

# (trackbar name, config attribute, scale, max slider value)
SLIDERS = [
    ("grip enter x100", "GRIP_ENTER", 100, 100),
    ("grip exit x100", "GRIP_EXIT", 100, 100),
    ("open below x100", "OPEN_BELOW", 100, 100),
    ("finger curled x100", "FINGER_CURLED", 100, 100),
    ("min fingers", "MIN_CURLED_FINGERS", 1, 4),
    ("pos min_cutoff x10", "POS_MIN_CUTOFF", 10, 50),
    ("pos beta x10", "POS_BETA", 10, 200),
    ("ang min_cutoff x10", "ANG_MIN_CUTOFF", 10, 50),
    ("ang beta x10", "ANG_BETA", 10, 50),
    ("side-on ratio x100", "SIDE_ON_RATIO", 100, 100),
]
TUNE_WIN = "vision tuning"
MAIN_WIN = "vision debug (Q quit, P print, C counter)"


class DebugSink:
    """Latest debug packet from the vision thread, plus a frame counter."""

    def __init__(self):
        self._lock = threading.Lock()
        self.packet = None
        self.seq = 0

    def __call__(self, packet):
        with self._lock:
            self.packet = packet
            self.seq += 1

    def latest(self):
        with self._lock:
            return self.seq, self.packet


def make_sliders():
    cv2.namedWindow(TUNE_WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(TUNE_WIN, 420, 40 * len(SLIDERS))
    for name, attr, scale, vmax in SLIDERS:
        cv2.createTrackbar(name, TUNE_WIN, int(round(getattr(config, attr) * scale)), vmax, lambda v: None)


def apply_sliders(vt):
    for name, attr, scale, _ in SLIDERS:
        v = cv2.getTrackbarPos(name, TUNE_WIN)
        if v < 0:
            return
        setattr(config, attr, v / scale if scale != 1 else int(v))
    p = vt.pipeline
    if p is not None:   # One Euro filters keep their own copies of the params
        p.blade.pos.min_cutoff = max(config.POS_MIN_CUTOFF, 0.05)
        p.blade.pos.beta = config.POS_BETA
        p.blade.ang._f.min_cutoff = max(config.ANG_MIN_CUTOFF, 0.05)
        p.blade.ang._f.beta = config.ANG_BETA


def print_tunables():
    print("\n# ---- paste into vision/config.py ----")
    for _, attr, _, _ in SLIDERS:
        print(f"{attr} = {getattr(config, attr)}")


def draw_hand(img, hand, colour, thick):
    h, w = img.shape[:2]
    pts = (hand.img[:, :2] * (w, h)).astype(int)
    for a, b in HAND_CONNECTIONS:
        cv2.line(img, tuple(pts[a]), tuple(pts[b]), colour, thick, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, tuple(p), 3, colour, -1, cv2.LINE_AA)
    cv2.putText(img, f"{hand.label} {hand.score:.2f}", tuple(pts[0] + (10, 22)), FONT, 0.6, colour, 2)


def draw_blade(img, base, angle, colour, thick):
    h, w = img.shape[:2]
    bx, by = base[0] * w, base[1] * h
    tip = (bx + BLADE_LEN_PX * math.cos(angle), by + BLADE_LEN_PX * math.sin(angle))
    cv2.line(img, (int(bx), int(by)), (int(tip[0]), int(tip[1])), colour, thick, cv2.LINE_AA)
    cv2.circle(img, (int(bx), int(by)), thick + 3, colour, -1, cv2.LINE_AA)


def text(panel, y, s, colour=(230, 230, 230), scale=0.5):
    cv2.putText(panel, s, (10, y), FONT, scale, colour, 1, cv2.LINE_AA)
    return y + int(28 * scale + 8)


def render(pkt, fps, ms_hist, extra_lines=()):
    frame = cv2.cvtColor(pkt["frame"], cv2.COLOR_RGB2BGR)
    f = pkt["fields"]
    sword, state = pkt["sword"], pkt["grip_state"]
    for hand in pkt["hands"]:
        if hand is not sword:
            draw_hand(frame, hand, (150, 150, 150), 1)
    if sword is not None:
        draw_hand(frame, sword, COLOURS[state], 2)
        if pkt["raw_angle"] is not None:
            from vision.geometry import blade_base
            draw_blade(frame, blade_base(sword.img), pkt["raw_angle"], (200, 200, 200), 1)
        draw_blade(frame, f["blade_base"], f["blade_angle"],
                   (255, 255, 255) if f["sword_active"] else (120, 120, 120), 4)

    panel = np.zeros((frame.shape[0], PANEL_W, 3), np.uint8)
    y = 26
    big = state if sword is not None else "NO HAND"
    if f["hands_in_frame"] == 2:
        big = "TWO HANDS"
    cv2.putText(panel, big, (10, y + 8), FONT, 1.0, COLOURS.get(state, (160, 160, 160)), 2)
    y += 40
    y = text(panel, y, f"hands_in_frame {f['hands_in_frame']}   held {pkt['held']}")
    y = text(panel, y, f"sword_visible {f['sword_visible']}  active {f['sword_active']}",
             (60, 220, 60) if f["sword_active"] else (230, 230, 230))
    y = text(panel, y, f"confidence {f['confidence']:.2f}   angle {math.degrees(f['blade_angle']):6.1f} deg")
    bb = f["blade_base"]
    y = text(panel, y, f"blade_base ({bb[0]:.3f}, {bb[1]:.3f})")
    fs = pkt["foreshorten"]
    y = text(panel, y, f"2D/3D {fs:.2f}  side-on {pkt['side_on']}" if fs is not None else "2D/3D -",
             (0, 200, 230) if pkt["side_on"] else (230, 230, 230))
    y += 4
    score = pkt["score"]
    y = text(panel, y, f"curl score {score:.2f}  fingers curled {pkt['n_curled']}" if score is not None
             else "curl score -")
    curls = pkt["curls"]
    bar_w = PANEL_W - 110
    for i, name in enumerate(FINGER_NAMES + ("SCORE",)):
        val = (curls[i] if i < 4 else score) if curls is not None else 0.0
        cv2.putText(panel, name, (10, y + 12), FONT, 0.45, (200, 200, 200), 1)
        x0 = 80
        cv2.rectangle(panel, (x0, y), (x0 + bar_w, y + 14), (60, 60, 60), -1)
        cv2.rectangle(panel, (x0, y), (x0 + int(bar_w * val), y + 14),
                      (60, 220, 60) if val >= (config.FINGER_CURLED if i < 4 else config.GRIP_ENTER)
                      else (120, 120, 200), -1)
        marks = [config.FINGER_CURLED] if i < 4 else [config.OPEN_BELOW, config.GRIP_EXIT, config.GRIP_ENTER]
        for m in marks:
            cv2.line(panel, (x0 + int(bar_w * m), y - 2), (x0 + int(bar_w * m), y + 16), (255, 255, 255), 1)
        y += 22
    y += 6
    y = text(panel, y, f"fps {fps:5.1f}")
    for key in ("frame_wait", "convert", "mediapipe", "grip", "smooth", "publish", "total"):
        vals = ms_hist[key]
        if vals:
            a = np.array(vals)
            y = text(panel, y, f"{key:<10} {a.mean():6.2f} ms   p95 {np.percentile(a, 95):6.2f}", scale=0.45)
    for line in extra_lines:
        y = text(panel, y, line, (0, 200, 230))
    return np.hstack([frame, panel])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=None)
    ap.add_argument("--no-sliders", action="store_true")
    args = ap.parse_args()

    shared = FakeShared()
    sink = DebugSink()
    stop = threading.Event()
    vt = start(shared.set_hand_state, shared.set_latest_frame, stop, sink, args.camera)
    if not args.no_sliders:
        make_sliders()
    cv2.namedWindow(MAIN_WIN, cv2.WINDOW_AUTOSIZE)

    ms_hist = {k: deque(maxlen=90) for k in
               ("frame_wait", "convert", "mediapipe", "grip", "smooth", "publish", "total")}
    stamps = deque(maxlen=30)
    last_seq = 0
    try:
        while True:
            seq, pkt = sink.latest()
            if pkt is not None and seq != last_seq:
                last_seq = seq
                stamps.append(pkt["t"])
                for k, v in pkt["ms"].items():
                    ms_hist[k].append(v)
                fps = (len(stamps) - 1) / (stamps[-1] - stamps[0]) if len(stamps) > 1 else 0.0
                cv2.imshow(MAIN_WIN, render(pkt, fps, ms_hist))
            elif pkt is None:
                wait = np.zeros((480, 640 + PANEL_W, 3), np.uint8)
                cv2.putText(wait, vt.error or "starting camera + MediaPipe...", (20, 240), FONT, 0.6,
                            (230, 230, 230), 1)
                cv2.imshow(MAIN_WIN, wait)
            key = cv2.waitKey(5) & 0xFF
            if not args.no_sliders:
                apply_sliders(vt)
            if key in (ord("q"), 27):
                break
            if key == ord("p"):
                print_tunables()
            if cv2.getWindowProperty(MAIN_WIN, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        stop.set()
        vt.join(timeout=2)
        cv2.destroyAllWindows()
        print_tunables()


if __name__ == "__main__":
    main()
