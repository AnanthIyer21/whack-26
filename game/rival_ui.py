"""The rival on screen: an avatar whose face shows the mood, and a typewriter speech bubble.

Placeholder faces are drawn in code until RBadiadka7's avatar/<mood>.png files arrive
(they are used automatically when present). Newest line replaces the old one at once.
"""
import math
import os

import pygame

SS = 3
MOODS = ("smug", "rattled", "defensive", "gloating")
LAUGH_FACES = ("laughing", "laughing2")   # two mouth frames, swapped quickly = cackling
LAUGH_TIME = 2.8                          # seconds GRIP-9000 cackles after you hit a bomb
TYPE_SPEED = 40          # characters per second
ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "avatar")


def _face(mood, size):
    S = size * SS
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S / 2
    R = S * 0.46
    head = {"smug": (120, 90, 200), "rattled": (90, 130, 200), "defensive": (200, 120, 60),
            "gloating": (200, 60, 110), "laughing": (215, 70, 120), "laughing2": (215, 70, 120)}[mood]
    pygame.draw.circle(s, (20, 20, 30), (c, c + S * 0.02), R + S * 0.02)
    pygame.draw.circle(s, head, (c, c), R)
    pygame.draw.circle(s, tuple(min(255, v + 50) for v in head), (c - R * 0.3, c - R * 0.35), R * 0.35)
    pygame.draw.circle(s, head, (c - R * 0.1, c - R * 0.1), R * 0.6)
    # visor
    visor = pygame.Rect(0, 0, R * 1.5, R * 0.55)
    visor.center = (c, c - R * 0.18)
    pygame.draw.rect(s, (15, 15, 25), visor, border_radius=int(R * 0.25))
    ex, ey, er = R * 0.38, c - R * 0.18, R * 0.13
    eye = (120, 255, 230)
    if mood == "smug":            # half-closed eyes
        for sx in (-1, 1):
            pygame.draw.ellipse(s, eye, (c + sx * ex - er, ey - er * 0.45, 2 * er, er * 0.9))
    elif mood == "rattled":       # wide eyes, sweat
        for sx in (-1, 1):
            pygame.draw.circle(s, eye, (c + sx * ex, ey), er * 1.2)
        pygame.draw.ellipse(s, (180, 230, 255), (c + R * 0.75, c - R * 0.6, R * 0.16, R * 0.28))
    elif mood == "defensive":     # angled brows
        for sx in (-1, 1):
            pygame.draw.circle(s, eye, (c + sx * ex, ey), er)
            pygame.draw.line(s, (255, 255, 255), (c + sx * (ex - er * 1.4), ey - er * 2.6),
                             (c + sx * (ex + er * 1.2), ey - er * 1.6), int(SS * 3))
    elif mood in LAUGH_FACES:     # laughing: eyes squeezed shut into chevrons, tears flying
        for sx in (-1, 1):
            cx_, w_ = c + sx * ex, er * 1.3
            # ">  <" : each eye points towards the middle
            pts = [(cx_ + sx * w_ * 0.6, ey - er * 0.8),
                   (cx_ - sx * w_ * 0.6, ey),
                   (cx_ + sx * w_ * 0.6, ey + er * 0.8)]
            pygame.draw.lines(s, eye, False, pts, int(SS * 3.5))
            tear = pygame.Rect(0, 0, R * 0.13, R * 0.2)
            tear.center = (c + sx * (R * 0.92), ey + R * (0.12 if mood == "laughing" else 0.2))
            pygame.draw.ellipse(s, (150, 215, 255), tear)
    else:                         # gloating: happy arcs
        for sx in (-1, 1):
            rect = pygame.Rect(0, 0, er * 2.4, er * 2.4)
            rect.center = (c + sx * ex, ey + er * 0.6)
            pygame.draw.arc(s, eye, rect, 0.2, math.pi - 0.2, int(SS * 3))
    # mouth
    my = c + R * 0.42
    if mood == "smug":
        pygame.draw.arc(s, (20, 20, 30), (c - R * 0.15, my - R * 0.25, R * 0.6, R * 0.35), math.pi * 1.1, math.pi * 1.9, int(SS * 3))
    elif mood == "rattled":
        pygame.draw.ellipse(s, (20, 20, 30), (c - R * 0.12, my - R * 0.1, R * 0.24, R * 0.3))
    elif mood == "defensive":
        pygame.draw.line(s, (20, 20, 30), (c - R * 0.3, my), (c + R * 0.3, my - R * 0.05), int(SS * 3))
    elif mood in LAUGH_FACES:     # big open cackle (frame 2 is a little more closed)
        h = R * (0.5 if mood == "laughing" else 0.36)
        mouth = pygame.Rect(0, 0, R * 0.9, h)
        mouth.midtop = (c, my - R * 0.12)
        pygame.draw.ellipse(s, (25, 15, 25), mouth)
        pygame.draw.rect(s, head, (mouth.x, mouth.y, mouth.w, mouth.h * 0.35))  # flat top lip
        tongue = pygame.Rect(0, 0, mouth.w * 0.45, mouth.h * 0.38)
        tongue.midbottom = (c, mouth.bottom - mouth.h * 0.06)
        pygame.draw.ellipse(s, (235, 90, 110), tongue)
    else:
        pygame.draw.arc(s, (20, 20, 30), (c - R * 0.4, my - R * 0.35, R * 0.8, R * 0.5), math.pi * 1.05, math.pi * 1.95, int(SS * 4))
    # antenna
    pygame.draw.line(s, (30, 30, 40), (c, c - R), (c, c - R * 1.08), int(SS * 3))
    return pygame.transform.smoothscale(s, (size, size)).convert_alpha()


_cache = {}


def face(mood, size):
    mood = mood if mood in MOODS or mood in LAUGH_FACES else "smug"
    key = (mood, size)
    if key not in _cache:
        img = None
        path = os.path.join(ASSET_DIR, mood + ".png")
        if os.path.exists(path):
            try:
                img = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (size, size))
            except pygame.error:
                img = None
        _cache[key] = img or _face(mood, size)
    return _cache[key]


def wrap(font, text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class RivalDisplay:
    """Holds the current line and draws avatar + bubble. Call show() for each new line."""

    def __init__(self, app, size=140):
        self.app = app
        self.size = size
        self.line = None
        self.shown_at = 0.0
        self.mood = "smug"
        self.laugh_t0 = -9.0
        self.laugh_dur = 0.0
        self.laugh_k = 0.0         # 0..1 how hard it's laughing
        self.has = []              # floating "HA"s: [t_start, dx, size, angle]

    def laugh(self, now, strength=1.0):
        """Point and laugh (the game calls this when you hit a bomb)."""
        strength = max(0.0, min(1.0, strength))
        if self.laughing(now):                    # another bomb mid-laugh: keep it going
            self.laugh_dur = max(self.laugh_dur, now - self.laugh_t0 + LAUGH_TIME * 0.7)
            return
        self.laugh_t0, self.laugh_k = now, strength
        self.laugh_dur = LAUGH_TIME
        # a stream of "HA"s over most of the laugh, alternating sides
        n = int(LAUGH_TIME / 0.32)
        self.has = [[now + i * 0.32, (-1) ** i * (8 + 10 * (i % 3)), int(30 + 12 * strength), (-1) ** i * 12]
                    for i in range(n)]

    def laughing(self, now):
        return now - self.laugh_t0 < self.laugh_dur

    def show(self, line, now):
        self.line, self.shown_at = line, now
        self.mood = line.get("mood", "smug")

    def sync(self, now):
        """Pick up the app's newest rival line if it's new."""
        if self.app.rival_line is not None and self.app.rival_line is not self.line:
            self.show(self.app.rival_line, now)

    def _draw_has(self, screen, now, avatar_center, size):
        alive = []
        for ha in self.has:
            t0, dx, fs, ang = ha
            age = now - t0
            if age < 0:
                alive.append(ha)
                continue
            if age > 0.9:
                continue
            alive.append(ha)
            u = age / 0.9
            pop = 1 + 0.5 * max(0.0, 1 - age / 0.1)
            x = avatar_center[0] - size * 0.6 + dx - 45 * u
            y = max(fs * 0.7, avatar_center[1] - size * 0.15 - 50 * u)   # stays on screen
            for col, off in (((150, 30, 70), (2, 2)), ((255, 255, 255), (0, 0))):
                img = self.app.render("HA", int(fs * pop), col)
                img = pygame.transform.rotozoom(img, ang + math.sin(now * 20) * 5, 1.0)
                img.set_alpha(int(255 * (1 - u * u)))
                screen.blit(img, img.get_rect(center=(x + off[0], y + off[1])))
        self.has = alive

    def current(self, now):
        """(text so far, alpha) or None when nothing is showing."""
        if not self.line:
            return None
        age = now - self.shown_at
        dur = float(self.line.get("duration", 2.5))
        text = self.line["text"]
        if age > dur + 0.4:
            self.mood = "smug"
            return None
        alpha = 255 if age <= dur else int(255 * (1 - (age - dur) / 0.4))
        return text[:max(0, int(age * TYPE_SPEED))], alpha

    def draw(self, screen, now, avatar_center, bubble_right, max_w=420, size=None, text_size=30,
             thinking=False, text_override=None):
        size = size or self.size
        bounce = 0.0
        if self.line:
            age = now - self.shown_at
            bounce = math.sin(min(1.0, age / 0.35) * math.pi) * 0.12 * max(0.0, 1 - age / 0.35)
        center = avatar_center
        if self.laughing(now):
            # cackling: mouth flaps, head bobs and shakes, tears fly, "HA"s float up
            age = now - self.laugh_t0
            fade = min(1.0, (self.laugh_dur - age) / 0.25)
            k = self.laugh_k * fade
            frame = LAUGH_FACES[int(now * 9) % 2]
            img = face(frame, size)
            img = pygame.transform.rotozoom(img, math.sin(now * 14) * 9 * k, 1 + 0.07 * k)
            center = (avatar_center[0] + math.sin(now * 23) * 3 * k,
                      avatar_center[1] - abs(math.sin(now * 18)) * 7 * k)
        else:
            img = face(self.mood, size)
            if bounce:
                img = pygame.transform.rotozoom(img, math.sin(now * 40) * 6 * bounce * 4, 1 + bounce)
        screen.blit(img, img.get_rect(center=center))
        self._draw_has(screen, now, avatar_center, size)

        cur = None
        if text_override is not None:
            cur = (text_override, 255)
        elif thinking:
            dots = "." * (1 + int(now * 3) % 3)
            cur = (dots, 255)
        else:
            cur = self.current(now)
        if not cur or not cur[0]:
            return
        text, alpha = cur
        font = self.app.font(text_size)
        lines = wrap(font, text, max_w - 36)
        lh = font.get_linesize()
        w = max(font.size(l)[0] for l in lines) + 36
        h = lh * len(lines) + 26
        bubble = pygame.Surface((w + 20, h), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (255, 255, 255, 240), (0, 0, w, h), border_radius=18)
        tail_y = min(h - 14, 30)
        pygame.draw.polygon(bubble, (255, 255, 255, 240), [(w - 4, tail_y - 10), (w + 18, tail_y), (w - 4, tail_y + 10)])
        for i, l in enumerate(lines):
            bubble.blit(font.render(l, True, (25, 25, 35)), (18, 13 + i * lh))
        bubble.set_alpha(alpha)
        screen.blit(bubble, (bubble_right - w - 20, avatar_center[1] - tail_y))
