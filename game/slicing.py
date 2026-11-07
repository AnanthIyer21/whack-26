"""Swept-blade collision. Pure maths, no pygame, so it can be unit-tested.

A blade is (base, angle, length). Between two samples the blade sweeps an area;
we split the move into small sub-steps and test each little quad (as two
triangles) against the fruit's circle.
"""
import math

SUBSTEP_PX = 40.0     # max movement per sub-step
SUBSTEP_RAD = 0.3     # max rotation per sub-step
MAX_SUBSTEPS = 16


def tip(base, angle, length):
    return (base[0] + math.cos(angle) * length, base[1] + math.sin(angle) * length)


def angle_diff(a, b):
    """Smallest signed difference b - a, in -pi..pi."""
    return (b - a + math.pi) % (2 * math.pi) - math.pi


def _seg_point_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    k = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    cx, cy = ax + k * dx, ay + k * dy
    return math.hypot(px - cx, py - cy)


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_triangle(p, a, b, c):
    d1, d2, d3 = _cross(a, b, p), _cross(b, c, p), _cross(c, a, p)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def circle_hits_triangle(c, r, a, b, d):
    if _in_triangle(c, a, b, d):
        return True
    return min(_seg_point_dist(c, a, b), _seg_point_dist(c, b, d), _seg_point_dist(c, d, a)) <= r


def swept_hit(base0, ang0, base1, ang1, length, center, radius):
    """True if the blade sweeping from (base0, ang0) to (base1, ang1) touches the circle."""
    tip0, tip1 = tip(base0, ang0, length), tip(base1, ang1, length)
    move = max(math.dist(base0, base1), math.dist(tip0, tip1))
    turn = abs(angle_diff(ang0, ang1))
    n = max(1, min(MAX_SUBSTEPS, math.ceil(max(move / SUBSTEP_PX, turn / SUBSTEP_RAD))))
    da = angle_diff(ang0, ang1)
    prev_b, prev_t = base0, tip0
    for i in range(1, n + 1):
        k = i / n
        b = (base0[0] + (base1[0] - base0[0]) * k, base0[1] + (base1[1] - base0[1]) * k)
        t = tip(b, ang0 + da * k, length)
        if circle_hits_triangle(center, radius, prev_b, prev_t, t) or \
           circle_hits_triangle(center, radius, prev_b, t, b):
            return True
        prev_b, prev_t = b, t
    return False
