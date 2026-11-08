"""Live grip/open reliability check for the pitch (RBadiadka7). Also records vision latency.

One run = one person, one hand: 20 GRIP + 20 OPEN prompts in random order (about 3 min).
Do it for all four of us, left and right hand, on the demo laptop.

    python tools/reliability_check.py --person Aaron --hand left
    python tools/reliability_check.py --person Aaron --hand right --lighting "venue, lamp on"
    python tools/reliability_check.py --person Test --hand left --fake      # no camera: keyboard

How a trial works
  READY  hold the OPPOSITE pose (so every trial is a real change of state), up to 3 s.
         Not reached -> SKIP, retried once at the end; not reached again -> FAIL "not_ready"
  GO     the prompt appears; you have 2.0 s to do it
  PASS   the pose is recognised for 0.3 s in a row, with exactly one hand in frame:
           GRIP -> HandState.sword_active (what the game plays on)
           OPEN -> the grip stabiliser says OPEN (UNCLEAR does NOT count as open)
  FAIL   otherwise; the reason is the most common wrong state in the window:
           wrong_state (saw the opposite), unclear, no_hand, two_hands

Keys   SPACE start / pause    R redo the last trial (it is logged, the old row marked superseded)
       ESC save and quit      (fake mode: hold G = grip, O = open, U = unclear, N = no hand, T = two hands)

Output (appended, committed):
  results/reliability.csv          one row per trial
  results/latency_vision.json      per-stage vision latency (mean, p95) from this session
Then: python tools/reliability_summary.py
"""
import argparse
import csv
import json
import os
import platform
import random
import sys
import threading
import time
from collections import Counter, deque

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pygame  # noqa: E402

import shared  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
CSV_PATH = os.path.join(RESULTS, "reliability.csv")
LATENCY_PATH = os.path.join(RESULTS, "latency_vision.json")
FIELDS = ["session", "ts", "machine", "person", "hand", "lighting", "trial", "prompt", "result", "reason",
          "reaction_ms", "mean_conf", "ready_ok", "redo", "superseded"]

READY_MAX = 3.0      # s to get into the opposite pose before the prompt
READY_HOLD = 0.3
WINDOW = 2.0         # s to perform the prompt
HOLD = 0.3           # s the pose must be held continuously
RESULT_SHOW = 0.7    # s the PASS / FAIL banner stays up
STAGES = ["frame_wait", "convert", "mediapipe", "grip", "smooth", "publish", "total"]

W, H = 1280, 720
BG, FG = (11, 11, 26), (244, 244, 248)
GREEN, RED, YELLOW, CYAN, MAGENTA = (60, 220, 120), (255, 70, 70), (255, 210, 60), (60, 242, 255), (255, 60, 172)


# ------------------------------------------------------------------------- input sources
class Observation:
    __slots__ = ("t", "state", "hands", "active", "conf")

    def __init__(self, t, state, hands, active, conf):
        self.t, self.state, self.hands, self.active, self.conf = t, state, hands, active, conf


class RealVision:
    """Aaron's vision loop on a thread; every processed frame becomes an Observation."""

    def __init__(self, camera):
        from vision.thread import start_thread
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.obs = deque()
        self.ms = {k: [] for k in STAGES}
        self.frames = 0
        self.first_t = None
        self.thread, self.loop = start_thread(self.stop, on_debug=self._on_debug, camera_index=camera)

    def _on_debug(self, d):
        f = d["fields"]
        o = Observation(d["t"], d.get("grip_state"), f["hands_in_frame"], f["sword_active"], f["confidence"])
        with self.lock:
            self.obs.append(o)
            self.frames += 1
            self.first_t = self.first_t or d["t"]
            self.last_t = d["t"]
            for k in STAGES:
                if k in d["ms"]:
                    self.ms[k].append(d["ms"][k])

    def drain(self, keys=None):
        with self.lock:
            out = list(self.obs)
            self.obs.clear()
        return out

    def frame(self):
        img, _ = shared.get_latest_frame()
        return img

    def error(self):
        return getattr(self.loop, "error", None)

    def fps(self):
        with self.lock:
            if not self.first_t or self.frames < 2 or self.last_t == self.first_t:
                return 0.0
            return (self.frames - 1) / (self.last_t - self.first_t)

    def close(self):
        self.stop.set()
        self.thread.join(2.0)


class FakeVision:
    """Keyboard stand-in so the tool can be tested without a camera."""

    def __init__(self):
        self.ms = {k: [] for k in STAGES}
        self.last = 0.0

    def drain(self, keys):
        now = time.monotonic()
        if now - self.last < 1 / 30:
            return []
        self.last = now
        if keys[pygame.K_t]:
            return [Observation(now, "GRIP", 2, False, 0.9)]
        if keys[pygame.K_n]:
            return [Observation(now, None, 0, False, 0.0)]
        state = "GRIP" if keys[pygame.K_g] else "UNCLEAR" if keys[pygame.K_u] else "OPEN" if keys[pygame.K_o] else "OPEN"
        return [Observation(now, state, 1, state == "GRIP", 0.95)]

    def frame(self):
        return None

    def error(self):
        return None

    def fps(self):
        return 30.0

    def close(self):
        pass


# ------------------------------------------------------------------------------ scoring
def matches(o, pose):
    if o.hands != 1:
        return False
    return o.active if pose == "GRIP" else (o.state == "OPEN" and not o.active)


def wrong_reason(o, pose):
    if o.hands == 0:
        return "no_hand"
    if o.hands >= 2:
        return "two_hands"
    if o.state == "UNCLEAR" or o.state is None:
        return "unclear"
    return "wrong_state"


class Trial:
    def __init__(self, index, prompt, last_chance=False):
        self.index, self.prompt, self.last_chance = index, prompt, last_chance
        self.opposite = "OPEN" if prompt == "GRIP" else "GRIP"
        self.phase = "ready"
        self.t0 = time.monotonic()
        self.ready_run = None
        self.ready_ok = False
        self.go_t = None
        self.run_start = None
        self.wrong = Counter()
        self.confs = []
        self.result = self.reason = None
        self.reaction_ms = None
        self.done_t = None

    def feed(self, obs, now):
        if self.phase == "ready":
            for o in obs:
                if matches(o, self.opposite):
                    self.ready_run = self.ready_run or o.t
                    if o.t - self.ready_run >= READY_HOLD:
                        self.ready_ok = True
                else:
                    self.ready_run = None
            if self.ready_ok:
                self.phase, self.go_t = "go", now
            elif now - self.t0 >= READY_MAX:      # never got into the starting pose
                self._finish("FAIL" if self.last_chance else "SKIP", "not_ready", None, now)
            return
        if self.phase != "go":
            return
        for o in obs:
            if o.t < self.go_t:
                continue                         # frame captured before the prompt appeared
            if matches(o, self.prompt):
                self.confs.append(o.conf)
                self.run_start = self.run_start or o.t
                if o.t - self.run_start >= HOLD:
                    self._finish("PASS", "", (self.run_start - self.go_t) * 1000, now)
                    return
            else:
                self.run_start = None
                self.wrong[wrong_reason(o, self.prompt)] += 1
        if now - self.go_t >= WINDOW:
            reason = self.wrong.most_common(1)[0][0] if self.wrong else "timeout"
            self._finish("FAIL", reason, None, now)

    def _finish(self, result, reason, reaction_ms, now):
        self.result, self.reason, self.reaction_ms = result, reason, reaction_ms
        self.phase, self.done_t = "done", now


# -------------------------------------------------------------------------------- output
def append_row(row):
    os.makedirs(RESULTS, exist_ok=True)
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def mark_superseded(session, trial_no):
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["session"] == session and r["trial"] == str(trial_no) and r["superseded"] == "0":
            r["superseded"] = "1"
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def save_latency(vision, session):
    """Merge this session's per-stage samples into results/latency_vision.json."""
    if not any(vision.ms.values()):
        return None
    data = {"sessions": {}}
    if os.path.exists(LATENCY_PATH):
        try:
            with open(LATENCY_PATH) as f:
                data = json.load(f)
        except (OSError, ValueError):
            pass
    data.setdefault("sessions", {})[session] = {
        "machine": platform.node(), "fps": round(vision.fps(), 1),
        "stages": [{"name": k, "mean_ms": round(float(np.mean(v)), 2), "p95_ms": round(float(np.percentile(v, 95)), 2),
                    "n": len(v)} for k, v in vision.ms.items() if v]}
    # headline numbers = every sample of the newest session (the slide reads "stages")
    data["stages"] = data["sessions"][session]["stages"]
    data["fps"] = data["sessions"][session]["fps"]
    data["source"] = "tools/reliability_check.py (vision on_debug timings, frame arrived -> HandState published)"
    with open(LATENCY_PATH, "w") as f:
        json.dump(data, f, indent=2)
    return data["stages"]


# ---------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Grip/open reliability check")
    ap.add_argument("--person", required=True)
    ap.add_argument("--hand", required=True, choices=["left", "right"])
    ap.add_argument("--trials", type=int, default=20, help="per pose (default 20 GRIP + 20 OPEN)")
    ap.add_argument("--lighting", default="")
    ap.add_argument("--camera", type=int, default=None)
    ap.add_argument("--fake", action="store_true", help="keyboard instead of the camera")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.SCALED)
    pygame.display.set_caption(f"reliability check - {args.person} ({args.hand} hand)")
    clock = pygame.time.Clock()
    font_path = os.path.join(ROOT, "assets", "fonts", "PressStart2P-Regular.ttf")

    def font(size):
        try:
            return pygame.font.Font(font_path, size)
        except (OSError, FileNotFoundError):
            return pygame.font.Font(None, size * 2)

    big, mid, small = font(72), font(22), font(14)
    try:
        pygame.mixer.init()
        beep = pygame.mixer.Sound(os.path.join(ROOT, "assets", "sounds", "sfx_countdown_beep.ogg"))
    except (pygame.error, FileNotFoundError):
        beep = None

    vision = FakeVision() if args.fake else RealVision(args.camera)
    session = time.strftime("%Y%m%d-%H%M%S") + f"-{args.person}-{args.hand}"
    machine = platform.node()
    rng = random.Random(args.seed)
    prompts = ["GRIP"] * args.trials + ["OPEN"] * args.trials
    rng.shuffle(prompts)
    queue = [(i + 1, p) for i, p in enumerate(prompts)]
    trial = None
    last_done = None          # (trial_no, prompt) of the last logged trial, for R
    redo_of = None
    retried = set()           # trial numbers already skipped once (not_ready)
    running = False
    log = []                  # (prompt, result) for the on-screen tally

    def row_for(t, redo):
        return {"session": session, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "machine": machine,
                "person": args.person, "hand": args.hand, "lighting": args.lighting, "trial": t.index,
                "prompt": t.prompt, "result": t.result, "reason": t.reason,
                "reaction_ms": "" if t.reaction_ms is None else round(t.reaction_ms),
                "mean_conf": round(float(np.mean(t.confs)), 3) if t.confs else "",
                "ready_ok": int(t.ready_ok), "redo": int(redo), "superseded": 0}

    quit_ = False
    while not quit_:
        now = time.monotonic()
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                quit_ = True
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                running = not running
                if running and trial is not None and trial.phase != "done":
                    trial = Trial(trial.index, trial.prompt)        # restart an interrupted trial
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_r and last_done and running:
                mark_superseded(session, last_done[0])
                if log:
                    log.pop()
                queue.insert(0, last_done)
                redo_of, last_done, trial = last_done[0], None, None
        keys = pygame.key.get_pressed()
        obs = vision.drain(keys)

        if running:
            if trial is None and queue:
                idx, pr = queue.pop(0)
                trial = Trial(idx, pr, last_chance=idx in retried)
            if trial is not None:
                was = trial.phase
                trial.feed(obs, now)
                if was == "ready" and trial.phase == "go" and beep:
                    beep.play()
                if trial.phase == "done" and trial.done_t == now:
                    redo = redo_of == trial.index
                    append_row(row_for(trial, redo))
                    redo_of = None
                    if trial.result == "SKIP":
                        retried.add(trial.index)
                        queue.append((trial.index, trial.prompt))
                    else:
                        log.append((trial.prompt, trial.result))
                        last_done = (trial.index, trial.prompt)
                if trial.phase == "done" and now - trial.done_t >= RESULT_SHOW:
                    trial = None
                    if not queue:
                        running = False

        # ---- draw
        screen.fill(BG)
        img = vision.frame()
        if img is not None:
            surf = pygame.image.frombuffer(np.ascontiguousarray(img).tobytes(), (img.shape[1], img.shape[0]), "RGB")
            surf = pygame.transform.scale(surf, (W, int(W * img.shape[0] / img.shape[1])))
            surf.set_alpha(110)
            screen.blit(surf, surf.get_rect(center=(W // 2, H // 2)))
        elif not args.fake:
            msg = vision.error() or "waiting for camera..."
            screen.blit(small.render(msg, True, YELLOW), (20, 90))

        n_done = len(log)
        total = len(prompts)
        header = f"{args.person} - {args.hand} hand   trial {min(n_done + 1, total)}/{total}"
        screen.blit(mid.render(header, True, FG), (20, 20))
        g = [r for p, r in log if p == "GRIP"]
        o = [r for p, r in log if p == "OPEN"]
        tally = (f"GRIP {g.count('PASS')}/{len(g)}   OPEN {o.count('PASS')}/{len(o)}   "
                 f"vision {vision.fps():4.1f} fps")
        screen.blit(small.render(tally, True, CYAN), (20, 56))

        def centre(text, f, colour, y):
            r = f.render(text, True, colour)
            screen.blit(r, r.get_rect(center=(W // 2, y)))

        if not running and not queue and trial is None:
            centre("DONE - thank you!", big, GREEN, H // 2 - 40)
            centre("ESC to save and quit", mid, FG, H // 2 + 50)
        elif not running:
            centre("PAUSED" if n_done else "READY?", big, YELLOW, H // 2 - 40)
            centre(f"one hand in view ({args.hand}).  SPACE to start", mid, FG, H // 2 + 50)
        elif trial is not None and trial.phase == "ready":
            centre(f"hold {trial.opposite}...", mid, FG, H // 2)
        elif trial is not None and trial.phase == "go":
            col = GREEN if trial.prompt == "GRIP" else MAGENTA
            centre("GRIP!" if trial.prompt == "GRIP" else "OPEN!", big, col, H // 2 - 20)
            frac = max(0.0, 1 - (now - trial.go_t) / WINDOW)
            pygame.draw.rect(screen, col, (W // 2 - 300, H // 2 + 60, int(600 * frac), 16))
        elif trial is not None and trial.phase == "done":
            ok = trial.result == "PASS"
            if trial.result == "SKIP":
                centre(f"couldn't see {trial.opposite} - will retry at the end", mid, YELLOW, H // 2)
            else:
                centre("PASS" if ok else f"MISS ({trial.reason})", big if ok else mid, GREEN if ok else RED, H // 2)

        help_ = "SPACE start/pause   R redo last   ESC save+quit"
        if args.fake:
            help_ += "  | G grip O open U unclear N none T two"
        screen.blit(small.render(help_, True, (150, 150, 170)), (20, H - 30))
        pygame.display.flip()
        clock.tick(60)

    stages = save_latency(vision, session)
    vision.close()
    pygame.quit()
    print(f"\nsaved {len(log)} trials to {os.path.relpath(CSV_PATH, ROOT)} (session {session})")
    if stages:
        print("vision latency this session:")
        for s in stages:
            print(f"  {s['name']:<11} mean {s['mean_ms']:6.2f} ms   p95 {s['p95_ms']:6.2f} ms   (n={s['n']})")
    print("summary: python tools/reliability_summary.py")


if __name__ == "__main__":
    main()
