"""Juice: particles, splats, pop-up text, screen shake."""
import math
import random

import pygame


class Particles:
    def __init__(self):
        self.items = []   # [x, y, vx, vy, life, max_life, size, colour, gravity]

    def burst(self, x, y, colour, n=16, speed=(150, 450), size=(3, 7), life=(0.4, 0.9), bias=None, gravity=900):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            if bias is not None and random.random() < 0.6:
                a = bias + random.uniform(-0.6, 0.6)
            v = random.uniform(*speed)
            lf = random.uniform(*life)
            self.items.append([x, y, math.cos(a) * v, math.sin(a) * v, lf, lf, random.uniform(*size), colour, gravity])

    def update(self, dt):
        for p in self.items:
            p[3] += p[8] * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
        self.items = [p for p in self.items if p[4] > 0]

    def draw(self, surface):
        for x, y, _, _, life, max_life, size, colour, _ in self.items:
            r = size * (0.4 + 0.6 * life / max_life)
            pygame.draw.circle(surface, colour, (int(x), int(y)), max(1, int(r)))


class Splats:
    """Juice stains on the background that fade out over a few seconds."""
    LIFE = 3.0

    def __init__(self):
        self.items = []   # [surface, pos, life]

    def add(self, x, y, colour, size):
        s = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
        c = size * 2
        for _ in range(9):
            a, d = random.uniform(0, math.tau), random.uniform(0, size * 0.9)
            pygame.draw.circle(s, (*colour, 150), (c + math.cos(a) * d, c + math.sin(a) * d), random.uniform(size * 0.25, size * 0.6))
        for _ in range(6):
            a, d = random.uniform(0, math.tau), random.uniform(size, size * 1.8)
            pygame.draw.circle(s, (*colour, 140), (c + math.cos(a) * d, c + math.sin(a) * d), random.uniform(2, 5))
        self.items.append([s, (x - c, y - c), self.LIFE])

    def update(self, dt):
        for it in self.items:
            it[2] -= dt
        self.items = [it for it in self.items if it[2] > 0]

    def draw(self, surface):
        for s, pos, life in self.items:
            s.set_alpha(int(255 * min(1.0, life / 1.0)))
            surface.blit(s, pos)


class Popups:
    """Text that punches in big, shrinks to size and floats up."""

    def __init__(self, font):
        self.font = font
        self.items = []   # [text, x, y, life, max_life, colour]

    def add(self, text, x, y, colour=(255, 215, 80), life=0.8):
        self.items.append([text, x, y, life, life, colour])

    def update(self, dt):
        for p in self.items:
            p[3] -= dt
            p[2] -= 50 * dt
        self.items = [p for p in self.items if p[3] > 0]

    def draw(self, surface):
        for text, x, y, life, max_life, colour in self.items:
            age = max_life - life
            scale = 1.0 + 0.6 * max(0.0, 1 - age / 0.15)
            alpha = int(255 * min(1.0, life / 0.25))
            img = self.font.render(text, True, colour)
            shadow = self.font.render(text, True, (0, 0, 0))
            if scale != 1.0:
                size = (int(img.get_width() * scale), int(img.get_height() * scale))
                img, shadow = pygame.transform.smoothscale(img, size), pygame.transform.smoothscale(shadow, size)
            img.set_alpha(alpha)
            shadow.set_alpha(alpha)
            r = img.get_rect(center=(x, y))
            surface.blit(shadow, r.move(3, 3))
            surface.blit(img, r)


class Shake:
    def __init__(self):
        self.time, self.strength = 0.0, 0.0

    def start(self, strength, time):
        self.strength, self.time = max(self.strength, strength), max(self.time, time)

    def update(self, dt):
        self.time = max(0.0, self.time - dt)
        if self.time == 0:
            self.strength = 0.0

    def offset(self):
        if self.time <= 0:
            return (0, 0)
        s = self.strength * min(1.0, self.time / 0.3)
        return (random.uniform(-s, s), random.uniform(-s, s))
