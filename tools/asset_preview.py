"""Interactive preview of everything in assets/, used the way the game will use it.

Usage:  python tools/asset_preview.py
Keys:   M = next rival mood        T = toggle talking
        mouse = sword points from its pivot at screen centre-left towards the cursor
        click = slice (plays a random slice + splat)
        1..9, 0, -, = = play each sound in the manifest     B = explosion
        G = game/title background  ESC = quit
Missing files are shown as magenta boxes / skipped, so it works before M2.
"""
import math
import os
import random
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import asset_spec as S  # noqa: E402

A = os.path.join(os.path.dirname(__file__), "..", "assets")
W, H = 1280, 720


def img(name):
    try:
        return pygame.image.load(os.path.join(A, name)).convert_alpha()
    except (pygame.error, FileNotFoundError):
        s = pygame.Surface(S.IMAGES.get(name, (64, 64)), pygame.SRCALPHA)
        s.fill((255, 0, 255, 160))
        return s


def snd(name):
    try:
        return pygame.mixer.Sound(os.path.join(A, name))
    except (pygame.error, FileNotFoundError):
        return None


def nine_slice(src, w, h, c=16):
    """Stretch a 9-slice image to w x h keeping c-px corners (how the game should draw the bubble)."""
    sw, sh = src.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    xs = [(0, c, 0, c), (c, sw - c, c, w - c), (sw - c, sw, w - c, w)]
    ys = [(0, c, 0, c), (c, sh - c, c, h - c), (sh - c, sh, h - c, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            part = src.subsurface((sx0, sy0, sx1 - sx0, sy1 - sy0))
            out.blit(pygame.transform.scale(part, (dx1 - dx0, dy1 - dy0)), (dx0, dy0))
    return out


def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("asset preview - RBadiadka7")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)
    try:
        bubble_font = pygame.font.Font(os.path.join(A, "fonts/PressStart2P-Regular.ttf"), 14)
    except (OSError, FileNotFoundError):
        bubble_font = pygame.font.Font(None, 26)

    bgs = [img("bg_game.png"), img("bg_title.png")]
    sword, glow = img("sword.png"), img("sword_glow.png")
    rivals = {(m, t): img(f"rival_{m}{'_talk' if t else ''}.png") for m in S.MOODS for t in (0, 1)}
    bubble, tail = img("bubble.png"), img("bubble_tail.png")
    fruit = {f: (img(f"fruit_{f}.png"), img(f"fruit_{f}_half_l.png"), img(f"fruit_{f}_half_r.png"),
                 img(f"splat_{f}.png")) for f in S.FRUITS}
    bomb = img("bomb.png")
    expl = [img(f"explosion_{i}.png") for i in range(6)]
    lives = img("life_full.png"), img("life_empty.png")
    sounds = [(p, snd(p)) for p in S.SOUNDS]
    keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
            pygame.K_8, pygame.K_9, pygame.K_0, pygame.K_MINUS, pygame.K_EQUALS, pygame.K_LEFTBRACKET,
            pygame.K_RIGHTBRACKET]

    mood_i, talking, bg_i = 0, True, 0
    pivot = (300, 420)
    trail = []
    halves = []      # [fruit, t0, x, y]
    expl_t0 = None
    lines = {"smug": "Is that a sword or a butter knife?", "rattled": "W-wait, that was luck.",
             "defensive": "I LET you have that one.", "gloating": "BOMB! Spectacular. Again!"}
    last = "-"

    while True:
        t = pygame.time.get_ticks() / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_m:
                    mood_i = (mood_i + 1) % len(S.MOODS)
                elif e.key == pygame.K_t:
                    talking = not talking
                elif e.key == pygame.K_g:
                    bg_i ^= 1
                elif e.key == pygame.K_b:
                    expl_t0 = t
                    s = dict(sounds).get("sounds/sfx_explosion.ogg")
                    s and s.play()
                elif e.key in keys:
                    p, s = sounds[keys.index(e.key)]
                    last = p + ("" if s else "  (MISSING)")
                    if s:
                        pygame.mixer.stop()
                        s.play()
            if e.type == pygame.MOUSEBUTTONDOWN:
                f = random.choice(S.FRUITS)
                halves.append([f, t, 760 + random.randint(-40, 40), 300])
                for name in (random.choice(S.SOUNDS[:3]), "sounds/sfx_splat.ogg"):
                    s = dict(sounds).get(name)
                    s and s.play()

        screen.blit(bgs[bg_i], (0, 0))

        # fruit row + lives + bomb
        for i, f in enumerate(S.FRUITS):
            screen.blit(fruit[f][0], (40 + i * 110, 40))
        screen.blit(bomb, (40 + 5 * 110, 40))
        for i in range(3):
            screen.blit(lives[0 if i < 2 else 1], (W - 190 + i * 56, 20))

        # sliced fruit flying apart, splat underneath
        for h in halves[:]:
            f, t0, x, y = h
            dt = t - t0
            if dt > 1.5:
                halves.remove(h)
                continue
            sp = fruit[f][3].copy()
            sp.set_alpha(int(255 * max(0, 1 - dt)))
            screen.blit(sp, sp.get_rect(center=(x, y)))
            for k, part in ((-1, fruit[f][1]), (1, fruit[f][2])):
                r = pygame.transform.rotate(part, -k * dt * 200)
                screen.blit(r, r.get_rect(center=(x + k * dt * 140, y - 80 * dt + 300 * dt * dt)))

        if expl_t0 is not None:
            i = int((t - expl_t0) / 0.06)
            if i < 6:
                screen.blit(expl[i], expl[i].get_rect(center=(40 + 5 * 110 + 48, 88)))
            else:
                expl_t0 = None

        # sword: rotate around pivot towards the mouse, glow (additive) then blade, then trail
        mx, my = pygame.mouse.get_pos()
        ang = math.atan2(my - pivot[1], mx - pivot[0])
        px, py = S.SWORD_PIVOT
        sw, sh = S.SWORD_SIZE
        for surf, flags in ((glow, pygame.BLEND_ADD), (sword, 0)):
            rot = pygame.transform.rotate(surf, -math.degrees(ang))
            # pivot offset from canvas centre, rotated
            ox, oy = px - sw / 2, py - sh / 2
            rx = ox * math.cos(ang) - oy * math.sin(ang)
            ry = ox * math.sin(ang) + oy * math.cos(ang)
            rect = rot.get_rect(center=(pivot[0] - rx, pivot[1] - ry))
            screen.blit(rot, rect, special_flags=flags)
        tip = (pivot[0] + (sw - px) * math.cos(ang), pivot[1] + (sw - px) * math.sin(ang))
        trail = (trail + [tip])[-12:]
        if len(trail) > 1:
            for i in range(1, len(trail)):
                pygame.draw.line(screen, (60, 242, 255), trail[i - 1], trail[i], max(1, i // 2))
        pygame.draw.circle(screen, (255, 60, 172), pivot, 4)

        # rival + bubble
        mood = S.MOODS[mood_i]
        frame = talking and int(t / 0.12) % 2
        screen.blit(rivals[(mood, frame)], (W - 300, H - 290))
        text = bubble_font.render(lines[mood], True, (11, 11, 26))
        bw, bh = text.get_width() + 40, text.get_height() + 32
        bx, by = W - 300 - bw + 60, H - 290 - bh + 10
        screen.blit(nine_slice(bubble, bw, bh), (bx, by))
        screen.blit(tail, (bx + bw - 60, by + bh - 4))
        screen.blit(text, (bx + 20, by + 16))

        help_ = [f"mood: {mood}  (M)   talking: {bool(talking)} (T)   bg: G   explode: B   click: slice",
                 "  ".join(f"{k}={os.path.basename(p)[4:-4]}" for k, (p, _) in
                           zip("1234567890-=[]", sounds) if p.split("/")[1].startswith("sfx")),
                 "music: " + "  ".join(f"{k}={os.path.basename(p)[:-4]}" for k, (p, _) in
                                       zip("1234567890-=[]", sounds) if "music" in p),
                 f"last sound: {last}"]
        for i, line in enumerate(help_):
            screen.blit(font.render(line, True, (244, 244, 248)), (20, H - 100 + i * 24))
        pygame.display.flip()
        clock.tick(60)
        snap = os.environ.get("PREVIEW_SNAPSHOT")  # headless self-test: save one frame and exit
        if snap and t > 0.5:
            pygame.image.save(screen, snap)
            return


if __name__ == "__main__":
    main()
