"""One Euro filter (Casiez, Roussel & Vogel, CHI 2012).

A low-pass filter whose cutoff rises with speed: heavy smoothing when the hand
is still (no jitter), light smoothing when it moves fast (no lag in a swing).
"""
import math

import numpy as np


def _alpha(cutoff, dt):
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    def __init__(self, min_cutoff, beta, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self._x = None
        self._dx = None
        self._t = None

    def __call__(self, x, t):
        x = np.asarray(x, dtype=np.float64)
        if self._x is None:
            self._x, self._dx, self._t = x.copy(), np.zeros_like(x), t
            return x.copy()
        dt = t - self._t
        if dt <= 0:
            return self._x.copy()
        self._t = t
        dx = (x - self._x) / dt
        a_d = _alpha(self.d_cutoff, dt)
        self._dx = a_d * dx + (1 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * float(np.linalg.norm(self._dx))
        a = _alpha(cutoff, dt)
        self._x = a * x + (1 - a) * self._x
        return self._x.copy()


class AngleFilter:
    """One Euro on the unit vector (cos a, sin a), so it never jumps at +-pi."""

    def __init__(self, min_cutoff, beta, d_cutoff=1.0):
        self._f = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def reset(self):
        self._f.reset()

    def __call__(self, angle, t):
        v = self._f(np.array([math.cos(angle), math.sin(angle)]), t)
        return math.atan2(v[1], v[0])


def lerp_angle(a, b, w):
    """Shortest-way blend from angle a to angle b by weight w in [0, 1]."""
    d = math.atan2(math.sin(b - a), math.cos(b - a))
    return a + d * w
