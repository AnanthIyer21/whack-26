"""Small pure-maths helpers (no pygame), so they are easy to unit test."""
import math


def wrap_angle(a):
    """Wrap an angle to [-pi, pi)."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def dist_point_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy))


def point_in_convex(px, py, poly):
    """True if the point is inside a convex polygon (either winding order)."""
    sign = 0
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        if cross != 0:
            s = 1 if cross > 0 else -1
            if sign == 0:
                sign = s
            elif s != sign:
                return False
    return True


def circle_hits_quad(cx, cy, r, quad):
    """Does a circle overlap a (possibly degenerate) quad?

    Each swept quad comes from one small substep, so it is convex (or a thin sliver/line),
    and edge-distance + point-inside covers every case.
    """
    n = len(quad)
    for i in range(n):
        ax, ay = quad[i]
        bx, by = quad[(i + 1) % n]
        if dist_point_segment(cx, cy, ax, ay, bx, by) <= r:
            return True
    return point_in_convex(cx, cy, quad)
