"""Generate the team-made pixel art into assets/.

Everything is drawn at 1/4 size on tiny pygame Surfaces (pixel-perfect, no
antialiasing), then scaled x4 with nearest-neighbour. Deterministic: run it
again and you get identical files.

Usage:  python tools/gen_art.py            # writes everything
        python tools/gen_art.py rival      # only names containing "rival"
"""
import math
import os
import random
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np  # noqa: E402
import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import asset_spec as S  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "assets")
K = S.SCALE

OUTLINE = (26, 11, 18)
WHITE = (244, 244, 248)
CYAN = (60, 242, 255)
MAGENTA = (255, 60, 172)
YELLOW = (255, 210, 60)


# ---------------------------------------------------------------- helpers
def canvas(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def opaque(s):
    return pygame.surfarray.array_alpha(s) > 0  # indexed [x, y]


def neighbours_any(m):
    d = np.zeros_like(m)
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def neighbours_all(m):
    e = m.copy()
    e[1:, :] &= m[:-1, :]
    e[:-1, :] &= m[1:, :]
    e[:, 1:] &= m[:, :-1]
    e[:, :-1] &= m[:, 1:]
    e[0, :] = e[-1, :] = False
    e[:, 0] = e[:, -1] = False
    return e


def paint(s, mask, color):
    for x, y in zip(*np.nonzero(mask)):
        s.set_at((int(x), int(y)), color)


def outline_outside(s, color=OUTLINE):
    m = opaque(s)
    paint(s, neighbours_any(m) & ~m, color)
    return s


def px(s, pts, color):
    for p in pts:
        s.set_at(p, color)


def up(s):
    return pygame.transform.scale(s, (s.get_width() * K, s.get_height() * K))


def save(s, name, scale=True):
    if FILTER and FILTER not in name:
        return
    out = up(s) if scale else s
    want = S.IMAGES.get(name)
    assert want is None or out.get_size() == want, (name, out.get_size(), want)
    pygame.image.save(out, os.path.join(OUT, name))
    print("wrote", name, out.get_size())


# ----------------------------------------------------------------- fruit
# Each fruit: (draw fn on a 24x24 canvas, flesh colour, seed colour or None, juice colour)
def draw_apple(s):
    pygame.draw.circle(s, (224, 48, 58), (12, 13), 9)
    pygame.draw.circle(s, (176, 28, 44), (14, 15), 6, 0)
    pygame.draw.circle(s, (224, 48, 58), (11, 12), 6, 0)
    px(s, [(12, 2), (12, 3), (12, 4)], (107, 58, 30))
    pygame.draw.ellipse(s, (79, 191, 79), (13, 2, 5, 3))
    px(s, [(8, 9), (8, 10), (9, 8)], WHITE)


def draw_orange(s):
    pygame.draw.circle(s, (255, 140, 26), (12, 13), 9)
    pygame.draw.circle(s, (230, 110, 10), (14, 15), 6)
    pygame.draw.circle(s, (255, 140, 26), (11, 12), 6)
    rnd = random.Random(2)
    for _ in range(10):
        x, y = rnd.randint(6, 18), rnd.randint(7, 19)
        if (x - 12) ** 2 + (y - 13) ** 2 < 60:
            s.set_at((x, y), (214, 100, 10))
    px(s, [(12, 4), (13, 3), (14, 3)], (79, 191, 79))
    px(s, [(8, 9), (8, 10), (9, 8)], (255, 220, 170))


def draw_watermelon(s):
    pygame.draw.ellipse(s, (30, 122, 52), (1, 4, 22, 17))
    for x0 in (4, 8, 12, 16, 20):
        for y in range(5, 21):
            x = x0 + (1 if (y // 3) % 2 else 0)
            if s.get_at((x, y)).a:
                s.set_at((x, y), (79, 191, 79))
    px(s, [(5, 8), (5, 9), (6, 7)], (170, 230, 170))


def draw_banana(s):
    pygame.draw.circle(s, (255, 225, 53), (13, 9), 11)
    pygame.draw.circle(s, (0, 0, 0, 0), (16, 5), 10)
    for x in range(24):
        for y in range(24):
            if s.get_at((x, y)).a and (x - 13) ** 2 + (y - 9) ** 2 > 81:
                s.set_at((x, y), (230, 190, 30))
    # trim and add brown tips
    for y in range(24):
        for x in range(24):
            if s.get_at((x, y)).a and (x < 2 or y > 20 or x > 22):
                s.set_at((x, y), (0, 0, 0, 0))
    m = opaque(s)
    xs, ys = np.nonzero(m)
    tips = [(int(xs[np.argmin(ys)]), int(ys.min())), (int(xs[np.argmax(xs)]), int(ys[np.argmax(xs)]))]
    for tx, ty in tips:
        s.set_at((tx, ty), (107, 58, 30))


def draw_strawberry(s):
    pygame.draw.polygon(s, (232, 37, 58), [(3, 8), (21, 8), (12, 22)])
    pygame.draw.circle(s, (232, 37, 58), (8, 10), 5)
    pygame.draw.circle(s, (232, 37, 58), (16, 10), 5)
    for x in range(24):
        for y in range(24):
            if s.get_at((x, y)).a and (x + 2 * y) % 5 == 0 and (x * 3 + y) % 4 == 0:
                s.set_at((x, y), (255, 225, 120))
    pygame.draw.polygon(s, (60, 170, 60), [(6, 5), (12, 8), (18, 5), (15, 8), (12, 3), (9, 8)])
    px(s, [(12, 1), (12, 2)], (60, 170, 60))
    px(s, [(7, 9), (7, 10)], WHITE)


FRUIT = {
    "apple": (draw_apple, (255, 240, 200), (107, 58, 30), (255, 230, 170)),
    "orange": (draw_orange, (255, 194, 102), None, (255, 160, 40)),
    "watermelon": (draw_watermelon, (255, 64, 96), (26, 11, 18), (255, 64, 96)),
    "banana": (draw_banana, (255, 245, 192), None, (255, 240, 150)),
    "strawberry": (draw_strawberry, (255, 128, 144), (255, 230, 230), (232, 37, 58)),
}


def fruit_body(name):
    s = canvas(24, 24)
    FRUIT[name][0](s)
    return s


def half(body, name, side):
    """Cut the fruit vertically through the middle of its shape; show flesh on the cut face."""
    _, flesh, seed, _ = FRUIT[name]
    s = body.copy()
    xs = np.nonzero(opaque(body).any(axis=1))[0]
    cut = int((xs.min() + xs.max() + 1) // 2)
    for x in range(24):
        if (side == "l" and x >= cut) or (side == "r" and x < cut):
            for y in range(24):
                s.set_at((x, y), (0, 0, 0, 0))
    m = opaque(s)
    inner = neighbours_all(neighbours_all(m))  # keep a 2 px rind
    band = np.zeros_like(m)
    if side == "l":
        band[cut - 5:cut, :] = True
    else:
        band[cut:cut + 5, :] = True
    face = inner & band
    paint(s, face, flesh)
    if seed:
        for x, y in zip(*np.nonzero(face)):
            if (x * 7 + y * 3) % 11 == 0:
                s.set_at((int(x), int(y)), seed)
    return outline_outside(s)


def splat(name):
    juice = FRUIT[name][3]
    s = canvas(32, 32)
    rnd = random.Random(name)
    c = (*juice, 200)
    pygame.draw.circle(s, c, (16, 16), 6)
    for _ in range(9):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(6, 13)
        r = rnd.randint(1, 3)
        pygame.draw.circle(s, c, (int(16 + d * math.cos(a)), int(16 + d * math.sin(a))), r)
        pygame.draw.line(s, c, (16, 16), (int(16 + d * 0.8 * math.cos(a)), int(16 + d * 0.8 * math.sin(a))), 2)
    return s


# ------------------------------------------------------------ bomb / fx
def bomb():
    s = canvas(24, 24)
    pygame.draw.circle(s, (38, 38, 58), (11, 14), 8)
    pygame.draw.circle(s, (70, 70, 100), (9, 12), 3)
    px(s, [(8, 10), (8, 11), (9, 10)], (150, 150, 190))
    pygame.draw.rect(s, (110, 110, 130), (12, 4, 4, 3))
    px(s, [(16, 3), (17, 2), (18, 2), (19, 1)], (200, 170, 120))
    outline_outside(s, (255, 64, 64))  # red outline: reads as danger on dark bg
    px(s, [(20, 0), (21, 1), (20, 1)], YELLOW)
    px(s, [(21, 0), (19, 0)], (255, 140, 26))
    return s


def explosion(i):
    s = canvas(48, 48)
    rnd = random.Random(i)
    r = 6 + i * 4
    fade = [255, 255, 240, 200, 140, 70][i]
    if i < 5:
        pygame.draw.circle(s, (255, 60, 40, fade), (24, 24), r)
        pygame.draw.circle(s, (255, 140, 26, fade), (24, 24), max(r - 3, 1))
        if i < 4:
            pygame.draw.circle(s, (255, 210, 60, fade), (24, 24), max(r - 6, 1))
        if i < 2:
            pygame.draw.circle(s, (255, 255, 255, fade), (24, 24), max(r - 9, 1))
    for _ in range(4 + i * 2):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(r * 0.6, r + 2)
        pr = rnd.randint(2, 4)
        col = (90, 90, 110, fade) if i >= 3 else (255, 210, 60, fade)
        pygame.draw.circle(s, col, (int(24 + d * math.cos(a)), int(24 + d * math.sin(a))), pr)
    return s


# ---------------------------------------------------------------- sword
def sword():
    s = canvas(72, 16)
    pygame.draw.rect(s, (107, 58, 30), (0, 6, 4, 4))          # handle (inside the fist)
    px(s, [(1, 6), (3, 9)], (160, 100, 60))
    pygame.draw.rect(s, YELLOW, (4, 3, 2, 10))                # guard, x=4 = pivot
    px(s, [(4, 3), (5, 12)], (200, 150, 30))
    pygame.draw.rect(s, (184, 212, 232), (6, 6, 62, 4))       # blade
    pygame.draw.line(s, (232, 246, 255), (6, 6), (67, 6))
    pygame.draw.line(s, (127, 160, 186), (6, 9), (67, 9))
    pygame.draw.line(s, (220, 240, 255), (8, 7), (60, 7))     # fuller shine
    pygame.draw.polygon(s, (184, 212, 232), [(68, 6), (71, 8), (68, 9)])
    return outline_outside(s)


def sword_glow():
    w, h = S.SWORD_SIZE
    x0, x1, y = 24, 258, 32  # 28 px clear of the right edge so the falloff ends inside
    xs = np.arange(w)[:, None].astype(float)
    ys = np.arange(h)[None, :].astype(float)
    dx = np.clip(xs, x0, x1) - xs
    d = np.sqrt(dx ** 2 + (ys - y) ** 2)
    f = np.clip(1 - d / 28.0, 0, 1) ** 2  # reaches exactly 0 before the canvas edge
    f[d < 6] = 1.0
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(s)
    for c in range(3):
        rgb[:, :, c] = (CYAN[c] * f).astype(np.uint8)
    del rgb
    a = pygame.surfarray.pixels_alpha(s)
    a[:, :] = (255 * f).astype(np.uint8)
    del a
    return s


# ---------------------------------------------------------------- lives
HEART = [
    "..XX..XX....",
    ".XXXXXXXX...",
    "XXXXXXXXXX..",
    "XXXXXXXXXX..",
    ".XXXXXXXX...",
    "..XXXXXX....",
    "...XXXX.....",
    "....XX......",
]


def life(full):
    s = canvas(12, 12)
    for y, row in enumerate(HEART):
        for x, ch in enumerate(row):
            if ch == "X":
                s.set_at((x + 1, y + 2), MAGENTA if full else (40, 40, 60))
    if full:
        px(s, [(3, 4), (3, 5)], WHITE)
    return outline_outside(s, OUTLINE if full else (110, 110, 140))


# ---------------------------------------------------------------- rival
BODY = (242, 179, 61)
BODY_DARK = (201, 130, 42)
LEAF = (60, 170, 60)
LEAF_DARK = (30, 110, 40)
GLASS = (17, 17, 24)
MOUTH = (58, 26, 10)
TONGUE = (224, 80, 106)


def pineapple(bristled=False):
    s = canvas(64, 64)
    # crown
    tall = 4 if bristled else 0
    leaves = [(-10, 10), (-5, 4 - tall), (0, 1 - tall), (5, 4 - tall), (10, 10), (-14, 15), (14, 15)]
    for dx, top in leaves:
        pygame.draw.polygon(s, LEAF, [(32 + dx - 3, 24), (32 + dx, top + 3), (32 + dx + 3, 24)])
        pygame.draw.line(s, LEAF_DARK, (32 + dx, top + 5), (32 + dx, 23))
    # body
    pygame.draw.ellipse(s, BODY, (14, 21, 36, 40))
    m = opaque(s)
    body = np.zeros_like(m)
    body[14:50, 21:61] = True
    for x, y in zip(*np.nonzero(m & body)):
        if y > 24 and ((x + y) % 7 == 0 or (x - y) % 7 == 0):
            s.set_at((int(x), int(y)), BODY_DARK)
    px(s, [(19, 32), (19, 33), (18, 35), (18, 36)], (255, 220, 140))
    return s


def glasses(s, dy=0, tilt=0):
    for lx, extra in ((19, 0), (34, tilt)):
        pygame.draw.rect(s, GLASS, (lx, 33 + dy + extra, 11, 6), border_radius=2)
        s.set_at((lx + 2, 34 + dy + extra), WHITE)
        s.set_at((lx + 3, 34 + dy + extra), (150, 150, 170))
    pygame.draw.line(s, GLASS, (30, 34 + dy + tilt // 2), (33, 34 + dy + tilt // 2))
    pygame.draw.line(s, GLASS, (17, 34 + dy), (19, 34 + dy))
    pygame.draw.line(s, GLASS, (45, 34 + dy + tilt), (47, 34 + dy + tilt))


def eye(s, x, y, pupil=(0, 0)):
    pygame.draw.rect(s, WHITE, (x, y, 5, 4))
    pygame.draw.rect(s, GLASS, (x + 1 + pupil[0], y + 1 + pupil[1], 2, 2))


def mouth_smug(s, talk):
    if talk:
        pygame.draw.ellipse(s, MOUTH, (30, 46, 9, 6))
        px(s, [(33, 50), (34, 50), (35, 50)], TONGUE)
    pygame.draw.lines(s, MOUTH, False, [(25, 49), (34, 49), (38, 47), (40, 45)])


def mouth_rattled(s, talk):
    if talk:
        pygame.draw.ellipse(s, MOUTH, (28, 47, 8, 8))
    else:
        pygame.draw.lines(s, MOUTH, False, [(25, 51), (27, 49), (29, 51), (31, 49), (33, 51), (35, 49), (37, 51)])


def mouth_defensive(s, talk):
    if talk:
        pygame.draw.rect(s, MOUTH, (26, 47, 12, 6))
        pygame.draw.line(s, WHITE, (27, 47), (36, 47))
    else:
        pygame.draw.lines(s, MOUTH, False, [(25, 52), (28, 49), (36, 49), (39, 52)])


def mouth_gloating(s, talk):
    h = 10 if talk else 7
    pygame.draw.rect(s, MOUTH, (22, 45, 20, h), border_bottom_left_radius=6, border_bottom_right_radius=6)
    pygame.draw.rect(s, WHITE, (23, 45, 18, 2))
    pygame.draw.ellipse(s, TONGUE, (28, 45 + h - 4, 8, 4))


def sparkle(s, x, y, c=YELLOW):
    px(s, [(x, y - 2), (x, y - 1), (x, y), (x, y + 1), (x, y + 2), (x - 2, y), (x - 1, y), (x + 1, y), (x + 2, y)], c)


def rival(mood, talk):
    if mood == "smug":
        s = pineapple()
        glasses(s)
        mouth_smug(s, talk)
    elif mood == "rattled":
        s = pineapple()
        eye(s, 21, 30, (1, 0))
        eye(s, 37, 30, (1, 0))
        glasses(s, dy=5, tilt=2)
        mouth_rattled(s, talk)
        pygame.draw.polygon(s, CYAN, [(50, 23), (48, 28), (52, 28)])
        pygame.draw.circle(s, CYAN, (50, 28), 2)
    elif mood == "defensive":
        s = pineapple(bristled=True)
        glasses(s)
        pygame.draw.line(s, (90, 50, 20), (19, 29), (28, 32))
        pygame.draw.line(s, (90, 50, 20), (45, 29), (36, 32))
        mouth_defensive(s, talk)
    else:  # gloating
        s = pineapple()
        glasses(s, dy=-8)
        for ex in (21, 37):  # happy closed eyes ^ ^
            px(s, [(ex, 38), (ex + 1, 37), (ex + 2, 36), (ex + 3, 37), (ex + 4, 38)], MOUTH)
        mouth_gloating(s, talk)
        sparkle(s, 54, 20)
        sparkle(s, 9, 28, WHITE)
    return outline_outside(s)


# --------------------------------------------------------------- bubble
def bubble():
    s = canvas(12, 12)
    pygame.draw.rect(s, OUTLINE, (0, 0, 12, 12), border_radius=3)
    pygame.draw.rect(s, WHITE, (1, 1, 10, 10), border_radius=2)
    return s


def bubble_tail():
    s = canvas(8, 8)
    pygame.draw.polygon(s, WHITE, [(2, 0), (7, 0), (0, 7)])
    pygame.draw.line(s, OUTLINE, (1, 0), (0, 7))   # left edge
    pygame.draw.line(s, OUTLINE, (7, 0), (0, 7))   # right edge (top stays open)
    return s


# ---------------------------------------------------------- backgrounds
def background(title):
    w, h, hz = 320, 180, 112
    s = pygame.Surface((w, h))
    top, bot = (11, 11, 26), (26, 11, 46)
    for y in range(h):
        t = y / h
        s.fill(tuple(int(a + (b - a) * t) for a, b in zip(top, bot)), (0, y, w, 1))
    rnd = random.Random(7)
    for _ in range(60):
        x, y = rnd.randrange(w), rnd.randrange(hz - 10)
        c = rnd.choice([(60, 60, 90), (90, 90, 130)] + ([(200, 200, 230)] if title else []))
        s.set_at((x, y), c)
    if title:  # striped neon sun behind the horizon
        for y in range(hz - 44, hz):
            if y > hz - 20 and (y // 3) % 2:
                continue
            half_w = int(math.sqrt(max(0, 40 ** 2 - (y - hz + 4) ** 2)))
            t = (y - (hz - 44)) / 44
            col = (255, int(210 - 150 * t), int(60 + 112 * t))
            s.fill(col, (160 - half_w, y, 2 * half_w, 1))
    grid = (70, 30, 110) if not title else (150, 40, 160)
    hor = (110, 40, 140) if not title else MAGENTA
    pygame.draw.line(s, hor, (0, hz), (w, hz))
    for i in range(-12, 13):
        pygame.draw.line(s, grid, (160 + i * 8, hz), (160 + i * 60, h))
    y, step = hz + 3, 3
    while y < h:
        pygame.draw.line(s, grid, (0, y), (w, y))
        step += 2
        y += step
    return s


# ----------------------------------------------------------------- main
FILTER = sys.argv[1] if len(sys.argv) > 1 else ""


def main():
    pygame.init()
    os.makedirs(OUT, exist_ok=True)
    for name in S.FRUITS:
        body = fruit_body(name)
        save(outline_outside(body.copy()), f"fruit_{name}.png")
        save(half(body, name, "l"), f"fruit_{name}_half_l.png")
        save(half(body, name, "r"), f"fruit_{name}_half_r.png")
        save(splat(name), f"splat_{name}.png")
    save(bomb(), "bomb.png")
    for i in range(6):
        save(explosion(i), f"explosion_{i}.png")
    save(sword(), "sword.png")
    save(sword_glow(), "sword_glow.png", scale=False)
    save(life(True), "life_full.png")
    save(life(False), "life_empty.png")
    for m in S.MOODS:
        save(rival(m, False), f"rival_{m}.png")
        save(rival(m, True), f"rival_{m}_talk.png")
    save(bubble(), "bubble.png")
    save(bubble_tail(), "bubble_tail.png")
    save(background(False), "bg_game.png")
    save(background(True), "bg_title.png")
    # Aliases at the paths the game on staging already loads (game/rival_ui.py, game/background.py)
    import shutil
    os.makedirs(os.path.join(OUT, "avatar"), exist_ok=True)
    for m in S.MOODS:
        shutil.copy(os.path.join(OUT, f"rival_{m}.png"), os.path.join(OUT, "avatar", f"{m}.png"))
    shutil.copy(os.path.join(OUT, "bg_game.png"), os.path.join(OUT, "background.png"))


if __name__ == "__main__":
    main()
