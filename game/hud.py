"""On-screen info during play: hearts + score top-left, timer top-centre, streak, popups."""
import math

import pygame

from . import config as C

SS = 3


def _heart(size, full):
    s = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    r = size * SS * 0.27
    cx, cy = size * SS / 2, size * SS * 0.42
    pts = [(cx - 2 * r * 0.98, cy + r * 0.25), (cx, cy + 2.15 * r), (cx + 2 * r * 0.98, cy + r * 0.25)]
    if full:
        col = (235, 50, 70)
        pygame.draw.circle(s, col, (cx - r, cy), r)
        pygame.draw.circle(s, col, (cx + r, cy), r)
        pygame.draw.polygon(s, col, pts)
        pygame.draw.circle(s, (255, 170, 180), (cx - r * 1.2, cy - r * 0.3), r * 0.35)
    else:
        col = (255, 255, 255, 110)
        w = int(SS * 2.5)
        pygame.draw.circle(s, col, (cx - r, cy), r, w, draw_top_left=True, draw_top_right=True)
        pygame.draw.circle(s, col, (cx + r, cy), r, w, draw_top_left=True, draw_top_right=True)
        pygame.draw.circle(s, col, (cx - r, cy), r, w, draw_bottom_left=True)
        pygame.draw.circle(s, col, (cx + r, cy), r, w, draw_bottom_right=True)
        pygame.draw.line(s, col, pts[0], pts[1], w)
        pygame.draw.line(s, col, pts[2], pts[1], w)
    return pygame.transform.smoothscale(s, (size, size)).convert_alpha()


class Popup:
    LIFE = 0.9

    def __init__(self, text, pos, color, size):
        self.text, self.x, self.y, self.color, self.size = text, pos[0], pos[1], color, size
        self.age = 0.0

    def step(self, dt):
        self.age += dt
        self.y -= 60 * dt
        return self.age < self.LIFE


class Hud:
    HEART = 46

    def __init__(self, app):
        self.app = app
        self.full = _heart(self.HEART, True)
        self.empty = _heart(self.HEART, False)
        self.lost_at = {}          # heart index -> time it was lost (for the crack animation)
        self.popups = []
        self.shown_points = 0.0    # score counts up smoothly

    def life_lost(self, index, now):
        self.lost_at[index] = now

    def popup(self, text, pos, color=(255, 255, 255), size=34):
        self.popups.append(Popup(text, pos, color, size))

    def update(self, dt, points):
        self.popups = [p for p in self.popups if p.step(dt)]
        self.shown_points += (points - self.shown_points) * min(1.0, 12 * dt)
        if abs(points - self.shown_points) < 0.5:
            self.shown_points = points

    def draw(self, screen, now, score, time_left, run_len):
        app = self.app
        # hearts: lost ones shake, swell and crack for 0.5 s, then become outlines
        for i in range(3):
            x, y = 20 + i * (self.HEART + 8), 16
            alive = i < score.lives
            lost = self.lost_at.get(i)
            if not alive and lost is not None and now - lost < 0.5:
                u = (now - lost) / 0.5
                jx = math.sin(u * 60) * 6 * (1 - u)
                img = pygame.transform.rotozoom(self.full, math.sin(u * 40) * 15 * (1 - u), 1 + 0.4 * u)
                img.set_alpha(int(255 * (1 - u)))
                screen.blit(self.empty, (x, y))
                screen.blit(img, img.get_rect(center=(x + self.HEART / 2 + jx, y + self.HEART / 2)))
                c = (x + self.HEART / 2, y + self.HEART / 2)
                pygame.draw.lines(screen, (40, 10, 15), False,
                                  [(c[0], c[1] - 14), (c[0] - 5, c[1] - 3), (c[0] + 4, c[1] + 4), (c[0] - 2, c[1] + 14)], 3)
            else:
                screen.blit(self.full if alive else self.empty, (x, y))

        # score
        app.text(screen, f"{int(round(self.shown_points))}", 64, (22, 66), (255, 255, 255))
        if score.streak >= 3:
            hot = score.doubled
            col = (255, 160, 60) if hot else (200, 220, 255)
            label = f"STREAK {score.streak}" + ("  x2" if hot else "")
            app.text(screen, label, 30, (24, 118), col)

        # timer: red and pulsing in the last 10 s
        secs = max(0, math.ceil(time_left))
        txt = f"{secs // 60}:{secs % 60:02d}"
        if time_left <= 10:
            pulse = 0.5 + 0.5 * math.sin(now * 2 * math.pi * 2)
            size = int(62 + 10 * pulse)
            app.text(screen, txt, size, (C.W // 2, 14), (255, int(80 + 60 * pulse), 80), "midtop")
        else:
            app.text(screen, txt, 62, (C.W // 2, 14), (255, 255, 255), "midtop")
        # thin progress bar under the timer
        frac = max(0.0, min(1.0, time_left / run_len)) if run_len else 0
        bar = pygame.Rect(C.W // 2 - 90, 66, 180, 5)
        pygame.draw.rect(screen, (70, 70, 90), bar, border_radius=3)
        pygame.draw.rect(screen, (255, 90, 80) if time_left <= 10 else (255, 255, 255),
                         pygame.Rect(bar.x, bar.y, int(bar.w * frac), bar.h), border_radius=3)

        for p in self.popups:
            u = p.age / p.LIFE
            pop = 1 + 0.35 * max(0.0, 1 - p.age / 0.12)     # quick pop-in
            img = app.render(p.text, int(p.size * pop), p.color)
            shadow = app.render(p.text, int(p.size * pop), (0, 0, 0))
            a = int(255 * (1 - u * u))
            img.set_alpha(a)
            shadow.set_alpha(a // 2)
            r = img.get_rect(center=(p.x, p.y))
            screen.blit(shadow, r.move(2, 3))
            screen.blit(img, r)
