"""Throws fruit and bombs up from the bottom, getting harder over the run.

Difficulty uses p = elapsed / run length (0 -> 1), so it scales to 30 s or 120 s runs.
  gap between throws 1.3 s -> 0.7 s   (x0.85 in the last 10 s)
  volley size        1      -> 3..5
  bomb chance        0 for the first 5 s, then 5% -> 20%  (max 1 per volley until p > 0.6)
  throw speed        x1.00  -> x1.15  (same arc height, just quicker)
"""
import math
import random

from . import config as C
from .entities import KINDS, Fruit, Bomb

GRAVITY = 1.16 * C.H        # px/s^2: a ~0.7 H rise takes ~1.1 s, about 2.2 s in the air
VOLLEY_STAGGER = 0.09       # seconds between launches inside one volley


def lerp(a, b, u):
    return a + (b - a) * max(0.0, min(1.0, u))


class Spawner:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.timer = 0.6            # first throw comes quickly
        self.queue = []             # (delay, factory) for staggered volley launches

    def params(self, elapsed, run_len):
        p = elapsed / run_len if run_len > 0 else 1.0
        gap = lerp(1.3, 0.7, p)
        if run_len - elapsed <= 10:
            gap *= 0.85
        n_min = 1 + int(round(lerp(0, 2, p)))          # 1 -> 3
        n_max = 1 + int(round(lerp(0, 4, p)))          # 1 -> 5
        bomb = 0.0 if elapsed < 5 else lerp(0.05, 0.20, p)
        max_bombs = 1 if p <= 0.6 else 2
        speed = lerp(1.0, 1.15, p)
        return gap, n_min, n_max, bomb, max_bombs, speed

    def update(self, dt, elapsed, run_len):
        """Advance time; returns the new Fruit/Bomb objects launched this frame."""
        out = []
        self.timer -= dt
        if self.timer <= 0:
            gap, n_min, n_max, bomb_p, max_bombs, speed = self.params(elapsed, run_len)
            self.timer += gap * self.rng.uniform(0.85, 1.15)
            n = self.rng.randint(n_min, n_max)
            bombs = 0
            for i in range(n):
                chance = bomb_p if n > 1 else bomb_p * 0.5   # lone bombs are rarer
                all_bombs = bombs == i and i == n - 1 and n > 1  # never a volley of only bombs
                is_bomb = bombs < max_bombs and not all_bombs and self.rng.random() < chance
                bombs += is_bomb
                self.queue.append([i * VOLLEY_STAGGER, is_bomb, speed])
        still = []
        for item in self.queue:
            item[0] -= dt
            if item[0] <= 0:
                out.append(self._throw(item[1], item[2]))
            else:
                still.append(item)
        self.queue = still
        return out

    def _throw(self, is_bomb, speed):
        rng = self.rng
        x = rng.uniform(0.15, 0.85) * C.W
        peak_y = rng.uniform(0.15, 0.45) * C.H
        g = GRAVITY * speed * speed
        r = 40
        rise = C.H + r - peak_y
        vy = -math.sqrt(2 * g * rise)
        airtime = 2 * math.sqrt(2 * rise / g)
        target = C.W / 2 + rng.uniform(-0.25, 0.25) * C.W   # drift towards the middle
        vx = (target - x) / airtime
        spin = rng.uniform(-200, 200)
        pos = (x, C.H + r)
        if is_bomb:
            return Bomb(pos, (vx, vy), g, spin)
        return Fruit(rng.choice(KINDS), pos, (vx, vy), g, spin)
