"""Fruit and bombs: flight physics, the spawner, and simple drawing."""
import math
import random

import pygame

from game import config


class Fruit:
    def __init__(self, kind, radius, colour, points, x, vx, vy):
        self.kind, self.r, self.colour, self.points = kind, radius, colour, points
        self.x, self.y = x, config.HEIGHT + radius
        self.vx, self.vy = vx, vy
        self.angle = random.uniform(0, math.tau)
        self.spin = random.uniform(-4, 4)
        self.alive = True

    @property
    def is_bomb(self):
        return self.kind == "bomb"

    def update(self, dt):
        self.vy += config.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt

    def fell_off(self):
        return self.vy > 0 and self.y - self.r > config.HEIGHT

    def draw(self, surface):
        pos = (int(self.x), int(self.y))
        if self.kind == "banana":
            w, h = self.r * 2.2, self.r * 1.0
            img = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(img, self.colour, img.get_rect())
            img = pygame.transform.rotate(img, -math.degrees(self.angle))
            surface.blit(img, img.get_rect(center=pos))
            return
        pygame.draw.circle(surface, self.colour, pos, self.r)
        # a highlight that spins with the fruit, so the spin is visible
        hx = self.x + math.cos(self.angle) * self.r * 0.45
        hy = self.y + math.sin(self.angle) * self.r * 0.45
        shine = (255, 255, 255) if self.kind != "bomb" else (90, 90, 100)
        pygame.draw.circle(surface, shine, (int(hx), int(hy)), max(3, self.r // 5))
        if self.is_bomb:
            pygame.draw.circle(surface, (230, 40, 30), (pos[0], pos[1] - self.r), 6)  # fuse spark
        if self.kind == "golden":
            pygame.draw.circle(surface, (255, 255, 200), pos, self.r, 3)


def throw(kind, radius, colour, points):
    """Make one fruit thrown up from the bottom so its peak is 40-85% up the screen."""
    W, H, g = config.WIDTH, config.HEIGHT, config.GRAVITY
    x = random.uniform(0.1, 0.9) * W
    peak_y = H * (1 - random.uniform(0.40, 0.85))
    vy = -math.sqrt(2 * g * (H + radius - peak_y))
    flight = 2 * -vy / g
    target_x = random.uniform(0.2, 0.8) * W
    vx = (target_x - x) / flight
    return Fruit(kind, radius, colour, points, x, vx, vy)


class Spawner:
    """Throws volleys; difficulty ramps from 0 to 1 over RAMP_SECONDS."""

    def __init__(self):
        self.timer = 0.8  # first throw comes quickly

    def update(self, dt, elapsed):
        d = min(1.0, elapsed / config.RAMP_SECONDS)
        self.timer -= dt
        if self.timer > 0:
            return []
        lo, hi = config.THROW_GAP
        self.timer = lo + (hi - lo) * d
        size = random.randint(1 + round(2 * d), 1 + round(4 * d))
        b_lo, b_hi = config.BOMB_CHANCE
        bomb_chance = b_lo + (b_hi - b_lo) * d
        out = []
        for _ in range(size):
            if random.random() < bomb_chance:
                out.append(throw(*config.BOMB))
            else:
                kind = random.choice(list(config.FRUITS))
                out.append(throw(kind, *config.FRUITS[kind]))
        if elapsed > config.GOLDEN_AFTER and random.random() < config.GOLDEN_CHANCE:
            out.append(throw(*config.GOLDEN))
        return out
