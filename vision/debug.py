"""Vision debug window (pygame; the team uses headless OpenCV, so no cv2.imshow).

Run:  .venv\\Scripts\\python -m vision.debug  [--camera 1]

Shows the mirrored camera with every hand's skeleton, the sword hand coloured
by grip state, the raw (thin) and smoothed (thick) blade, per-finger curl bars,
hands_in_frame, the HandState being published, fps and ms per stage, and a
tuning list at the bottom.

Bottom strip: last 3 s, one cell per frame. green GRIP, red OPEN, yellow UNCLEAR,
blue HELD (MediaPipe missed the hand, grace period covering it), black NO HAND,
purple TWO HANDS.

Keys:  Q / Esc quit   P print current tunables (paste them into vision/config.py)
       R reset the dropout / grip counters
       B switch blade mode: grip (across the fist) <-> knuckle (wrist -> knuckle)
       Up / Down pick a tunable, Left / Right change it (hold Shift for big steps)
       C counter mode (reliability check, coming in step 6)
"""
import argparse
import math
import threading
from collections import deque

import cv2
import numpy as np

from vision import config
from vision.geometry import FINGER_NAMES
from vision.stabiliser import GRIP, OPEN, UNCLEAR
from vision.thread import start_thread
from vision.tracker import HAND_CONNECTIONS

PANEL_W = 330
BLADE_LEN_PX = 170          # debug-only; the game uses shared.BLADE_LENGTH
COLOURS = {GRIP: (60, 220, 60), OPEN: (60, 60, 230), UNCLEAR: (0, 200, 230), None: (160, 160, 160)}
FONT = cv2.FONT_HERSHEY_SIMPLEX   # colours in this file are BGR (OpenCV drawing)

# (label, config attribute, step, min, max)
TUNABLES = [
    ("grip enter", "GRIP_ENTER", 0.01, 0.0, 1.0),
    ("grip exit", "GRIP_EXIT", 0.01, 0.0, 1.0),
    ("open below", "OPEN_BELOW", 0.01, 0.0, 1.0),
    ("finger curled", "FINGER_CURLED", 0.01, 0.0, 1.0),
    ("min fingers", "MIN_CURLED_FINGERS", 1, 1, 4),
    ("pos min_cutoff", "POS_MIN_CUTOFF", 0.1, 0.1, 5.0),
    ("pos beta", "POS_BETA", 0.1, 0.0, 20.0),
    ("ang min_cutoff", "ANG_MIN_CUTOFF", 0.1, 0.1, 5.0),
    ("ang beta", "ANG_BETA", 0.1, 0.0, 5.0),
    ("side-on ratio", "SIDE_ON_RATIO", 0.01, 0.0, 1.0),
    ("grace (s)", "LOST_GRACE_S", 0.01, 0.0, 0.5),
    ("coast damping", "COAST_DAMPING", 0.5, 0.0, 30.0),
]
TUNE_ROW_H = 18
TUNE_H = TUNE_ROW_H * ((len(TUNABLES) + 1) // 2) + 10


TIMELINE_COLOURS = {"GRIP": (60, 220, 60), "OPEN": (60, 60, 230), "UNCLEAR": (0, 200, 230),
                    "HELD": (230, 120, 30), "NONE": (0, 0, 0), "TWO": (200, 60, 200)}


def frame_code(pkt):
    f = pkt["fields"]
    if f["hands_in_frame"] == 0:
        return "NONE"
    if pkt["held"]:
        return "HELD"
    if f["hands_in_frame"] == 2:
        return "TWO"
    return pkt["grip_state"]


class DebugSink:
    """Latest debug packet from the vision thread, plus a per-frame timeline and
    dropout counters (recorded for EVERY frame, even ones the window skips)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.packet = None
        self.seq = 0
        self.timeline = deque(maxlen=90)     # last 3 s of frame codes
        self.reset_counts()

    def reset_counts(self):
        self.counts = dict(frames=0, missed=0, dropouts=0, lost=0, grip_on=0, grip_off=0)
        self._prev = None

    def __call__(self, packet):
        code = frame_code(packet)
        with self._lock:
            self.packet = packet
            self.seq += 1
            self.timeline.append(code)
            c, prev = self.counts, self._prev
            c["frames"] += 1
            if code == "HELD":
                c["missed"] += 1                      # MediaPipe saw nothing this frame
                if prev != "HELD":
                    c["dropouts"] += 1                # a new dropout started
            if code == "NONE" and prev not in (None, "NONE"):
                c["lost"] += 1                        # dropout outlasted the grace period
            if code == "GRIP" and prev not in ("GRIP", "HELD"):
                c["grip_on"] += 1
            if prev == "GRIP" and code in ("OPEN", "UNCLEAR"):
                c["grip_off"] += 1
            self._prev = code

    def summary(self):
        with self._lock:
            return dict(self.counts), list(self.timeline)

    def latest(self):
        with self._lock:
            return self.seq, self.packet


def adjust_tunable(index, direction, big, loop):
    label, attr, step, lo, hi = TUNABLES[index]
    integer = isinstance(step, int)
    step = step * (10 if big else 1)
    v = min(hi, max(lo, getattr(config, attr) + direction * step))
    setattr(config, attr, int(round(v)) if integer else round(v, 4))
    p = loop.pipeline
    if p is not None:   # One Euro filters keep their own copies of the params
        p.blade.pos.min_cutoff = config.POS_MIN_CUTOFF
        p.blade.pos.beta = config.POS_BETA
        p.blade.ang._f.min_cutoff = config.ANG_MIN_CUTOFF
        p.blade.ang._f.beta = config.ANG_BETA


def draw_tunables(width, selected):
    img = np.full((TUNE_H, width, 3), 25, np.uint8)
    col_w = width // 2
    for i, (label, attr, _, _, _) in enumerate(TUNABLES):
        x = 10 + col_w * (i % 2)
        y = 18 + TUNE_ROW_H * (i // 2)
        sel = i == selected
        colour = (0, 220, 255) if sel else (200, 200, 200)
        cv2.putText(img, f"{'>' if sel else ' '} {label:<15} {getattr(config, attr)}", (x, y), FONT, 0.45,
                    colour, 1, cv2.LINE_AA)
    return img


def print_tunables():
    print("\n# ---- paste into vision/config.py ----")
    for _, attr, _, _, _ in TUNABLES:
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
    if config.BLADE_MODE == "grip" and thick > 1:   # hilt stub out of the pinky side
        pommel = (bx - 45 * math.cos(angle), by - 45 * math.sin(angle))
        cv2.line(img, (int(bx), int(by)), (int(pommel[0]), int(pommel[1])), (40, 90, 160), thick + 2,
                 cv2.LINE_AA)


def text(panel, y, s, colour=(230, 230, 230), scale=0.5):
    cv2.putText(panel, s, (10, y), FONT, scale, colour, 1, cv2.LINE_AA)
    return y + int(28 * scale + 8)


def draw_timeline(frame, timeline):
    h, w = frame.shape[:2]
    cell = w / 90                      # timeline is a list copy of the last 90 frames
    y0 = h - 16
    cv2.rectangle(frame, (0, y0 - 2), (w, h), (40, 40, 40), -1)
    for i, code in enumerate(timeline):
        x0 = int(i * cell)
        cv2.rectangle(frame, (x0, y0), (int((i + 1) * cell) - 1, h - 2), TIMELINE_COLOURS[code], -1)


def render(pkt, fps, ms_hist, extra_lines=(), timeline=None):
    frame = cv2.cvtColor(pkt["frame"], cv2.COLOR_RGB2BGR)
    if timeline is not None:
        draw_timeline(frame, timeline)
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
    y = text(panel, y, f"blade_base ({bb[0]:.3f}, {bb[1]:.3f})  mode {config.BLADE_MODE}")
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
    for i, line in enumerate(extra_lines):       # on the camera image, top-left
        yy = 22 + 22 * i
        cv2.rectangle(frame, (4, yy - 16), (12 + 9 * len(line), yy + 6), (0, 0, 0), -1)
        cv2.putText(frame, line, (8, yy), FONT, 0.5, (0, 220, 255), 1, cv2.LINE_AA)
    return np.hstack([frame, panel])


def to_surface(pygame, bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return pygame.image.frombuffer(rgb.tobytes(), (rgb.shape[1], rgb.shape[0]), "RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=None)
    args = ap.parse_args()

    import pygame
    pygame.init()
    width = 640 + PANEL_W
    screen = pygame.display.set_mode((width, 480 + TUNE_H))
    pygame.display.set_caption("vision debug  (Q quit, P print, R reset, B blade mode, arrows tune)")
    clock = pygame.time.Clock()

    sink = DebugSink()
    stop = threading.Event()
    thread, loop = start_thread(stop, sink, args.camera)

    ms_hist = {k: deque(maxlen=90) for k in
               ("frame_wait", "convert", "mediapipe", "grip", "smooth", "publish", "total")}
    stamps = deque(maxlen=30)
    last_seq = 0
    selected = 0
    running = True
    try:
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    big = bool(ev.mod & pygame.KMOD_SHIFT)
                    if ev.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif ev.key == pygame.K_p:
                        print_tunables()
                    elif ev.key == pygame.K_r:
                        sink.reset_counts()
                    elif ev.key == pygame.K_b:
                        config.BLADE_MODE = "knuckle" if config.BLADE_MODE == "grip" else "grip"
                        if loop.pipeline is not None:
                            loop.pipeline.blade.reset()
                        print("blade mode:", config.BLADE_MODE)
                    elif ev.key == pygame.K_UP:
                        selected = (selected - 1) % len(TUNABLES)
                    elif ev.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(TUNABLES)
                    elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        adjust_tunable(selected, 1 if ev.key == pygame.K_RIGHT else -1, big, loop)

            seq, pkt = sink.latest()
            if pkt is not None and seq != last_seq:
                last_seq = seq
                stamps.append(pkt["t"])
                for k, v in pkt["ms"].items():
                    ms_hist[k].append(v)
                fps = (len(stamps) - 1) / (stamps[-1] - stamps[0]) if len(stamps) > 1 else 0.0
                c, tl = sink.summary()     # locked copy: the vision thread keeps appending
                lines = [f"missed frames {c['missed']}/{c['frames']}  dropouts {c['dropouts']}",
                         f"lost (>grace) {c['lost']}  grip on {c['grip_on']} off {c['grip_off']}",
                         "R resets counters"]
                screen.blit(to_surface(pygame, render(pkt, fps, ms_hist, lines, tl)), (0, 0))
            elif pkt is None:
                wait = np.zeros((480, width, 3), np.uint8)
                cv2.putText(wait, loop.error or "starting camera + MediaPipe...", (20, 240), FONT, 0.6,
                            (230, 230, 230), 1)
                screen.blit(to_surface(pygame, wait), (0, 0))
            screen.blit(to_surface(pygame, draw_tunables(width, selected)), (0, 480))
            pygame.display.flip()
            clock.tick(60)
    finally:
        stop.set()
        thread.join(timeout=2)
        pygame.quit()
        print_tunables()
        c, _ = sink.summary()
        print("\n# ---- session counters (since last R) ----")
        print(f"frames {c['frames']}  missed {c['missed']} ({100 * c['missed'] / max(c['frames'], 1):.1f}%)  "
              f"dropouts {c['dropouts']}  lost {c['lost']}  grip on {c['grip_on']}  grip off {c['grip_off']}")
        for k, v in ms_hist.items():
            if v:
                a = np.array(v)
                print(f"{k:<10} mean {a.mean():6.2f} ms  p95 {np.percentile(a, 95):6.2f} ms")


if __name__ == "__main__":
    main()
