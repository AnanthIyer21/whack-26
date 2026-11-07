"""Small UI kit: mouse buttons, dim overlays and the fist-hold ring."""
import math

import pygame

from . import config as C

FIST_HOLD = 0.7      # seconds of a steady fist to start / play again


class Button:
    def __init__(self, label, center, size=(260, 64), selected=False, danger=False):
        self.label = label
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center
        self.selected = selected
        self.danger = danger
        self.hover = 0.0

    def clicked(self, ev):
        return (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                and self.rect.collidepoint(ev.pos))

    def contains_mouse(self):
        return self.rect.collidepoint(pygame.mouse.get_pos())

    def draw(self, app, screen, dt=1 / 60):
        target = 1.0 if self.contains_mouse() else 0.0
        self.hover += (target - self.hover) * min(1.0, 14 * dt)
        r = self.rect.inflate(int(10 * self.hover), int(6 * self.hover))
        if self.danger:
            base, edge = (150, 40, 50), (255, 120, 120)
        elif self.selected:
            base, edge = (240, 190, 60), (255, 240, 170)
        else:
            base, edge = (40, 44, 70), (150, 160, 210)
        fill = tuple(int(c + (255 - c) * 0.12 * self.hover) for c in base)
        shadow = r.move(0, 5)
        pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=16)
        pygame.draw.rect(screen, fill, r, border_radius=16)
        pygame.draw.rect(screen, edge, r, 3, border_radius=16)
        col = (30, 25, 10) if self.selected else (255, 255, 255)
        app.text(screen, self.label, 40, r.center, col, "center")


def dim(screen, surf, alpha):
    surf.set_alpha(int(alpha))
    screen.blit(surf, (0, 0))


def fist_ring(screen, pos, progress, now):
    """A ring that fills while you hold a fist (progress 0..1)."""
    x, y = int(pos[0]), int(pos[1])
    r = 46
    pygame.draw.circle(screen, (255, 255, 255), (x, y), r, 3)
    if progress > 0:
        rect = pygame.Rect(0, 0, 2 * r + 12, 2 * r + 12)
        rect.center = (x, y)
        start = math.pi / 2
        pygame.draw.arc(screen, (255, 210, 80), rect, start, start + 2 * math.pi * progress, 9)


class FistHold:
    """Tracks a steady fist. Requires the hand to be NOT gripping first if `need_release`
    (so a fist still closed from the last run doesn't instantly restart)."""

    def __init__(self, need_release=False):
        self.held = 0.0
        self.released = not need_release

    def update(self, good, dt, blocked=False):
        if not good:
            self.released = True
            self.held = 0.0
            return False
        if not self.released or blocked:
            self.held = 0.0
            return False
        self.held += dt
        return self.held >= FIST_HOLD

    @property
    def progress(self):
        return min(1.0, self.held / FIST_HOLD)


def center_x():
    return C.W // 2
