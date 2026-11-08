"""Render the pitch numbers slide (1920x1080 PNG) from the measured data (RBadiadka7).

    python tools/make_numbers_slide.py
    python tools/make_numbers_slide.py --game-fps 60 --out results/numbers_slide.png

Reads (anything missing shows as "pending", the slide still renders):
  results/latency_vision.json   per-stage vision latency   (tools/reliability_check.py)
  results/reliability.json      grip/open reliability      (tools/reliability_summary.py)
  logs/latency.csv              event -> voice latency     (the rival, when run with --rival real)
  results/perf.json             optional {"game_fps": 60, "motion_to_photon_ms": 80}
Run it on the demo laptop after the reliability check and a few real-rival runs.
"""
import argparse
import csv
import json
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
W, H = 1920, 1080

# Dark slide, matching the game. Stage colours validated (dataviz validator, dark, surface PANEL):
# lightness band, chroma, CVD separation, normal-vision floor and contrast all pass.
BG = (11, 11, 26)
PANEL = (21, 21, 42)
INK = (240, 239, 236)
INK2 = (195, 194, 183)
MUTED = (130, 130, 150)
ACCENT = (255, 60, 172)          # titles only, never data
STAGE_COLOURS = [(0x39, 0x87, 0xE5), (0xD9, 0x59, 0x26), (0x19, 0x9E, 0x70), (0xC9, 0x85, 0x00), (0xD5, 0x51, 0x81)]
STAGES = [("convert", "camera -> RGB"), ("mediapipe", "MediaPipe landmarks"), ("grip", "our grip maths"),
          ("smooth", "our smoothing + blade"), ("publish", "publish HandState")]


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def rival_latency(path):
    """Group logs/latency.csv the same way tools/latency_report.py does; mean and p95 per group."""
    try:
        from tools.latency_report import group_of
    except Exception:
        return None
    if not os.path.exists(path):
        return None
    groups = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                g = group_of(row)
                if g.startswith("bank fallback"):
                    g = "bank fallback"                  # offline / timeout fallbacks: one row
                groups.setdefault(g, []).append(float(row["event_to_audio_ms"]))
            except (KeyError, ValueError):
                continue
    return {k: (float(np.mean(v)), float(np.percentile(v, 95)), len(v)) for k, v in groups.items()} or None


class Painter:
    def __init__(self, surf):
        self.s = surf
        pix = os.path.join(ROOT, "assets", "fonts", "PressStart2P-Regular.ttf")
        self.pix = {}
        self.sans = {}
        self.pix_path = pix if os.path.exists(pix) else None

    def font(self, size, pixel=False):
        cache = self.pix if pixel else self.sans
        if size not in cache:
            cache[size] = pygame.font.Font(self.pix_path if pixel else None, size)
        return cache[size]

    def text(self, s, size, pos, colour=INK, pixel=False, anchor="topleft"):
        img = self.font(size, pixel).render(s, True, colour)
        r = img.get_rect(**{anchor: pos})
        self.s.blit(img, r)
        return r

    def panel(self, rect, title):
        pygame.draw.rect(self.s, PANEL, rect, border_radius=18)
        self.text(title, 22, (rect.x + 36, rect.y + 32), INK2, pixel=True)

    def pending(self, rect, what):
        self.text("pending", 40, (rect.x + 36, rect.y + 110), MUTED, pixel=True)
        self.text(what, 30, (rect.x + 36, rect.y + 180), MUTED)


def draw_vision(p, rect, vis):
    p.panel(rect, "HAND -> GAME")
    if not vis or not vis.get("stages"):
        return p.pending(rect, "run tools/reliability_check.py on the demo laptop")
    st = {s["name"]: s for s in vis["stages"]}
    tot = st.get("total")
    if tot:
        r = p.text(f"{tot['mean_ms']:.0f} ms", 64, (rect.x + 36, rect.y + 88), INK, pixel=True)
        p.text(f"mean, camera frame -> HandState   (p95 {tot['p95_ms']:.0f} ms)", 30, (r.right + 28, r.y + 6), INK2)
        p.text(f"vision at {vis.get('fps', 0):.0f} fps, {tot['n']} frames measured live", 28, (r.right + 28, r.y + 40),
               MUTED)
    # one stacked bar of stage means, 2 px surface gaps, direct labels + legend
    parts = [(lbl, st[k]["mean_ms"], st[k]["p95_ms"], c) for (k, lbl), c in zip(STAGES, STAGE_COLOURS) if k in st]
    total = sum(m for _, m, _, _ in parts) or 1.0
    bx, by, bw, bh = rect.x + 36, rect.y + 196, rect.w - 72, 40
    x = bx
    for i, (lbl, m, _, c) in enumerate(parts):
        w = max(4, int(bw * m / total))
        if i == len(parts) - 1:
            w = bx + bw - x
        pygame.draw.rect(p.s, c, (x, by, max(w - 2, 2), bh), border_radius=4)
        x += w
    y = by + bh + 20
    for i, (lbl, m, p95, c) in enumerate(parts):
        col, row = i % 2, i // 2
        cx, cy = bx + col * (bw // 2), y + row * 34
        pygame.draw.rect(p.s, c, (cx, cy + 4, 16, 16), border_radius=3)
        p.text(f"{lbl}  {m:.1f} ms  (p95 {p95:.1f})", 25, (cx + 26, cy), INK2)


def draw_reliability(p, rect, rel):
    p.panel(rect, "GRIP / OPEN RECOGNISED")
    if not rel or not rel.get("overall") or not rel["overall"].get("n"):
        return p.pending(rect, "run the reliability check, then tools/reliability_summary.py")
    o = rel["overall"]
    r = p.text(f"{o['overall_pct']:.0f}%", 88, (rect.x + 36, rect.y + 84), INK, pixel=True)
    p.text(f"grip {o['grip_pct']:.0f}%   open {o['open_pct']:.0f}%", 32, (r.right + 32, r.y + 4), INK2)
    p.text(f"{o['n']} live trials, {o['people']} people, left + right hand", 28, (r.right + 32, r.y + 44), MUTED)
    if o.get("median_reaction_ms"):
        p.text(f"median {o['median_reaction_ms']:.0f} ms from prompt to recognised", 28, (r.right + 32, r.y + 76), MUTED)
    # small table: person x hand overall %
    y = rect.y + 206
    rows = rel.get("rows", [])
    people = sorted({x["person"] for x in rows})
    p.text("left", 25, (rect.x + 380, y), MUTED)
    p.text("right", 25, (rect.x + 520, y), MUTED)
    for i, person in enumerate(people[:4]):
        yy = y + 30 + i * 29
        p.text(person, 25, (rect.x + 36, yy), INK2)
        for hand, xx in (("left", 380), ("right", 520)):
            cell = next((x for x in rows if x["person"] == person and x["hand"] == hand), None)
            p.text("-" if not cell or cell["overall_pct"] is None else f"{cell['overall_pct']:.0f}%", 25,
                   (rect.x + xx, yy), INK)


def draw_rival(p, rect, riv):
    p.panel(rect, "EVENT -> GRIP-9000'S VOICE")
    if not riv:
        return p.pending(rect, "play a few runs with --rival real (logs/latency.csv)")
    order = ["bank line", "pre-fetched Claude line (pre-voiced)", "live Claude: other big moments",
             "live Claude: game over roast", "bank fallback"]
    names = {"bank line": "saved line", "pre-fetched Claude line (pre-voiced)": "Claude line, pre-voiced",
             "live Claude: other big moments": "live Claude line", "live Claude: game over roast": "live game over roast",
             "bank fallback": "saved line (Claude skipped)"}
    keys = [k for k in order if k in riv] + sorted(k for k in riv if k not in order)
    y = rect.y + 84
    p.text("mean", 26, (rect.x + 560, y), MUTED)
    p.text("p95", 26, (rect.x + 720, y), MUTED)
    for k in keys[:5]:
        mean, p95, n = riv[k]
        y += 42
        p.text(names.get(k, k), 30, (rect.x + 36, y), INK2)
        p.text(f"{mean:,.0f} ms", 30, (rect.x + 560, y), INK)
        p.text(f"{p95:,.0f} ms", 30, (rect.x + 720, y), INK)
    p.text("Claude only writes the big moments; everything else is instant.", 25,
           (rect.x + 36, rect.bottom - 44), MUTED)


def draw_game(p, rect, perf, vis, game_fps):
    p.panel(rect, "THE GAME")
    fps = game_fps or (perf or {}).get("game_fps")
    if not fps:
        return p.pending(rect, "pass --game-fps (smoke test prints it)")
    r = p.text(f"{fps:.0f} fps", 64, (rect.x + 36, rect.y + 88), INK, pixel=True)
    p.text("pygame, 3 threads: game / vision / rival", 30, (r.right + 28, r.y + 6), INK2)
    lines = []
    if vis and vis.get("fps"):
        lines.append(f"camera + hand tracking at {vis['fps']:.0f} fps")
    m2p = (perf or {}).get("motion_to_photon_ms")
    if m2p:
        lines.append(f"hand move -> on screen: {m2p:.0f} ms")
    lines.append("auto-pause the moment your grip or hand count changes")
    for i, s in enumerate(lines):
        p.text(s, 30, (rect.x + 36, rect.y + 200 + i * 44), INK2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "numbers_slide.png"))
    ap.add_argument("--vision", default=os.path.join(ROOT, "results", "latency_vision.json"))
    ap.add_argument("--reliability", default=os.path.join(ROOT, "results", "reliability.json"))
    ap.add_argument("--rival", default=os.path.join(ROOT, "logs", "latency.csv"))
    ap.add_argument("--perf", default=os.path.join(ROOT, "results", "perf.json"))
    ap.add_argument("--game-fps", type=float, default=None)
    args = ap.parse_args()

    pygame.init()
    s = pygame.Surface((W, H))
    s.fill(BG)
    p = Painter(s)
    p.text("GRIP-9000 REACTS IN THE MOMENT", 44, (72, 64), INK, pixel=True)
    p.text("Measured live on the demo laptop", 34, (72, 130), INK2)
    pygame.draw.rect(s, ACCENT, (72, 178, 220, 6), border_radius=3)

    gx, gy, gap = 72, 206, 32
    pw, ph = (W - 2 * gx - gap) // 2, (H - gy - 96 - gap) // 2
    a = pygame.Rect(gx, gy, pw, ph)
    b = pygame.Rect(gx + pw + gap, gy, pw, ph)
    c = pygame.Rect(gx, gy + ph + gap, pw, ph)
    d = pygame.Rect(gx + pw + gap, gy + ph + gap, pw, ph)
    vis = load_json(args.vision)
    draw_vision(p, a, vis)
    draw_reliability(p, b, load_json(args.reliability))
    draw_rival(p, c, rival_latency(args.rival))
    draw_game(p, d, load_json(args.perf), vis, args.game_fps)

    p.text("MediaPipe hand landmarks + our own grip maths and smoothing (nothing trained).  "
           "Claude writes the big-moment roasts; ElevenLabs voices them.", 28, (72, H - 62), MUTED)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    pygame.image.save(s, args.out)
    print("wrote", os.path.relpath(args.out, ROOT))


if __name__ == "__main__":
    main()
