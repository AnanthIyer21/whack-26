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

    def draw(self, surface, t=0.0):
        from game import art
        img = pygame.transform.rotate(art.fruit_sprite(self.kind, self.r), -math.degrees(self.angle))
        if self.is_bomb:
            # pulsing red danger glow behind the bomb, and a flickering fuse spark
            glow = 0.5 + 0.5 * math.sin(t * 12)
            pygame.draw.circle(surface, (120 + int(100 * glow), 20, 20), (int(self.x), int(self.y)), int(self.r * 1.25), 4)
        surface.blit(img, img.get_rect(center=(int(self.x), int(self.y))))
        if self.is_bomb:
            fx = self.x + math.cos(self.angle - 1.2) * self.r * 1.45
            fy = self.y + math.sin(self.angle - 1.2) * self.r * 1.45
            for i in range(3):
                pygame.draw.circle(surface, [(255, 240, 120), (255, 150, 30), (255, 60, 20)][i],
                                   (int(fx + random.uniform(-3, 3)), int(fy + random.uniform(-3, 3))), 6 - i * 2)


class Half:
    """One cut half of a fruit, flying apart and spinning."""

    def __init__(self, img, x, y, vx, vy, angle, spin):
        self.img, self.x, self.y, self.vx, self.vy = img, x, y, vx, vy
        self.angle, self.spin = angle, spin

    def update(self, dt):
        self.vy += config.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt

    def gone(self):
        return self.y > config.HEIGHT + 120

    def draw(self, surface):
        img = pygame.transform.rotate(self.img, -math.degrees(self.angle))
        surface.blit(img, img.get_rect(center=(int(self.x), int(self.y))))


def split(fruit, cut_angle):
    """Two Halves whose cut line lines up with the swing direction."""
    from game import art
    top, bottom = art.half_sprites(fruit.kind, fruit.r)
    nx, ny = math.sin(cut_angle), -math.cos(cut_angle)   # direction of the 'top' half
    out = []
    for img, sgn in ((top, 1), (bottom, -1)):
        out.append(Half(img, fruit.x + nx * sgn * 6, fruit.y + ny * sgn * 6,
                        fruit.vx + nx * sgn * 160, fruit.vy + ny * sgn * 160 - 60,
                        cut_angle, fruit.spin * 0.3 + sgn * 2.0))
    return out


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
