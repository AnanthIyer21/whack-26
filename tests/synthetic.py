"""Synthetic 21-point hands for tests: finger joints bent by chosen angles."""
import math

import numpy as np
from vision.tracker import DetectedHand

# Knuckle (MCP) positions relative to the wrist, metres; palm points up (-y).
_MCP = {5: (-0.025, -0.085), 9: (0.0, -0.090), 13: (0.020, -0.085), 17: (0.038, -0.075)}
_SEG = (0.040, 0.025, 0.022)   # proximal, middle, distal phalanx lengths


def _rot_x(deg):
    r = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])


def make_hand(bends=(0, 0, 0), rotation=None, thumb_curled=False):
    """bends = (MCP, PIP, DIP) bend in degrees applied to all 4 fingers; fingers curl
    toward -z (towards the camera). rotation: optional 3x3 applied to the whole hand."""
    pts = np.zeros((21, 3))
    for mcp, (x, y) in _MCP.items():
        pts[mcp] = (x, y, 0.0)
        palm_dir = np.array([x, y, 0.0]) / np.linalg.norm([x, y])
        d = palm_dir
        cum = 0.0
        p = pts[mcp].copy()
        for j, (bend, seg) in enumerate(zip(bends, _SEG)):
            cum += bend
            # Rotate the palm direction about the finger's own sideways axis.
            side = np.cross(palm_dir, [0, 0, 1.0])
            side /= np.linalg.norm(side)
            r = math.radians(cum)
            d = palm_dir * math.cos(r) + np.cross(side, palm_dir) * math.sin(r)
            p = p + d * seg
            pts[mcp + 1 + j] = p
    # Thumb: roughly out to the side.
    for k, (x, y) in enumerate([(-0.03, -0.02), (-0.05, -0.04), (-0.06, -0.06), (-0.065, -0.075)]):
        pts[1 + k] = (x * (0.5 if thumb_curled else 1.0), y, 0.0)
    if rotation is not None:
        pts = pts @ np.asarray(rotation).T
    return pts


def fist(**kw):
    return make_hand((85, 100, 60), **kw)


def open_hand(**kw):
    return make_hand((5, 5, 3), **kw)


def half_curl(**kw):
    return make_hand((35, 40, 20), **kw)


def detected(world, x=0.5, y=0.5, label="Right", score=0.95, scale=1.5):
    """Wrap world points as a DetectedHand with a fake image projection at (x, y)."""
    img = np.zeros((21, 3), dtype=np.float32)
    img[:, 0] = x + world[:, 0] * scale
    img[:, 1] = y + world[:, 1] * scale
    img[:, 2] = world[:, 2] * scale
    return DetectedHand(img=img, world=world.astype(np.float32), label=label, score=score)


ROT_X = _rot_x
