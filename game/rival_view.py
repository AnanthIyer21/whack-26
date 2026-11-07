"""The rival on screen: a smug code-drawn face whose expression follows its mood, and a speech bubble.

RB's art at assets/rival_<mood>.png (about 128 px) replaces the drawn face automatically.
"""
import math

import pygame

from game import assets, config

MOODS = ("smug", "rattled", "defensive", "gloating")
TYPE_SPEED = 40      # characters per second
FADE = 0.3


class RivalView:
    def __init__(self, font):
        self.font = font
        self.center = (config.WIDTH - 80, 84)
        self.mood = "smug"
        self.mood_left = 0.0
        self.text, self.shown, self.hold, self.age = "", 0.0, 0.0, 0.0
        self.clock = 0.0

    def clear(self):
        self.text, self.mood, self.mood_left = "", "smug", 0.0

    def say(self, line):
        """A rival_lines dict: {"text", "mood", "duration"}. A new line replaces the current one."""
        self.text = str(line.get("text", ""))
        self.set_mood(line.get("mood", "smug"), float(line.get("duration", 3.0)))
        typing = len(self.text) / TYPE_SPEED
        self.hold = max(float(line.get("duration", 3.0)), typing + 1.0)
        self.shown, self.age = 0.0, 0.0

    def set_mood(self, mood, duration):
        self.mood = mood if mood in MOODS else "smug"
        self.mood_left = duration + 0.5

    def update(self, dt):
        self.clock += dt
        self.age += dt
        self.shown = min(len(self.text), self.shown + TYPE_SPEED * dt)
        self.mood_left -= dt
        if self.mood_left <= 0:
            self.mood = "smug"
        if self.text and self.age > self.hold + FADE:
            self.text = ""

    # ---------------- drawing ----------------
    def draw(self, surface):
        self._draw_face(surface)
        if self.text:
            alpha = 255 if self.age < self.hold else int(255 * max(0, 1 - (self.age - self.hold) / FADE))
            self._draw_bubble(surface, self.text[:int(self.shown)], alpha)

    def _draw_face(self, surface):
        cx, cy = self.center
        m, t = self.mood, self.clock
        if m == "rattled":
            cx += math.sin(t * 40) * 3
        elif m == "gloating":
            cy -= abs(math.sin(t * 8)) * 8
        img = assets.image(f"rival_{m}", (128, 128))
        if img:
            surface.blit(img, img.get_rect(center=(cx, cy)))
            return
        R = 52
        head = {"smug": (120, 90, 200), "rattled": (150, 110, 200), "defensive": (170, 80, 120), "gloating": (110, 80, 210)}[m]
        pygame.draw.circle(surface, (0, 0, 0), (cx + 3, cy + 4), R)
        pygame.draw.circle(surface, head, (cx, cy), R)
        pygame.draw.circle(surface, tuple(min(255, c + 50) for c in head), (cx - 16, cy - 18), 14)
        pygame.draw.circle(surface, (30, 20, 50), (cx, cy), R, 3)
        ex, ey = 18, -8
        for side in (-1, 1):
            x = cx + side * ex
            pygame.draw.ellipse(surface, (250, 250, 250), (x - 11, cy + ey - 9, 22, 18))
            look = math.sin(t * 0.7) * 3
            pygame.draw.circle(surface, (20, 20, 30), (x + look, cy + ey + 1), 5)
            if m == "smug":       # half-closed lids
                pygame.draw.rect(surface, head, (x - 12, cy + ey - 10, 24, 9))
            elif m == "defensive":
                pygame.draw.rect(surface, head, (x - 12, cy + ey - 10, 24, 7))
            # eyebrows
            if m == "smug":
                pts = [(x - 12, cy + ey - 12 - (6 if side == 1 else 0)), (x + 12, cy + ey - 14)]
            elif m == "rattled":
                pts = [(x - 12 * side, cy + ey - 16), (x + 12 * side, cy + ey - 20)]
            elif m == "defensive":
                pts = [(x - 12 * side, cy + ey - 18), (x + 12 * side, cy + ey - 11)]
            else:
                pts = [(x - 12, cy + ey - 19), (x + 12, cy + ey - 19)]
            pygame.draw.line(surface, (30, 20, 50), pts[0], pts[1], 4)
        my = cy + 24
        if m == "smug":
            pygame.draw.arc(surface, (30, 20, 50), (cx - 6, my - 14, 30, 18), math.pi * 1.1, math.pi * 1.9, 4)
        elif m == "rattled":
            pts = [(cx - 16 + i * 4, my + (3 if i % 2 else -3)) for i in range(9)]
            pygame.draw.lines(surface, (30, 20, 50), False, pts, 3)
            drop = (cx + R - 6, cy - 20 + (t * 30) % 20)
            pygame.draw.circle(surface, (120, 200, 255), drop, 6)
        elif m == "defensive":
            pygame.draw.arc(surface, (30, 20, 50), (cx - 14, my - 2, 28, 16), 0.2, math.pi - 0.2, 4)
        else:
            pygame.draw.ellipse(surface, (40, 10, 30), (cx - 20, my - 10, 40, 22))
            pygame.draw.rect(surface, (250, 250, 250), (cx - 16, my - 10, 32, 7))
        label = self.font.render("RIVAL", True, (220, 210, 255))
        surface.blit(label, label.get_rect(center=(self.center[0], self.center[1] + R + 16)))

    def _draw_bubble(self, surface, text, alpha):
        max_w = 430
        lines, cur = [], ""
        for word in text.split():
            test = (cur + " " + word).strip()
            if self.font.size(test)[0] > max_w and cur:
                lines.append(cur)
                cur = word
            else:
                cur = test
        if cur:
            lines.append(cur)
        if not lines:
            return
        lh = self.font.get_linesize()
        w = max(self.font.size(line)[0] for line in lines) + 32
        h = lh * len(lines) + 22
        layer = pygame.Surface((w + 20, h + 6), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, w, h)
        pygame.draw.rect(layer, (0, 0, 0, 90), rect.move(3, 4), border_radius=16)
        pygame.draw.rect(layer, (252, 250, 245), rect, border_radius=16)
        pygame.draw.rect(layer, (40, 30, 60), rect, 3, border_radius=16)
        pygame.draw.polygon(layer, (252, 250, 245), [(w - 4, 18), (w + 18, 26), (w - 4, 34)])
        pygame.draw.lines(layer, (40, 30, 60), False, [(w - 2, 18), (w + 18, 26), (w - 2, 34)], 3)
        for i, line in enumerate(lines):
            layer.blit(self.font.render(line, True, (30, 20, 40)), (16, 11 + i * lh))
        layer.set_alpha(alpha)
        surface.blit(layer, (self.center[0] - 70 - w - 18, self.center[1] - 40))
