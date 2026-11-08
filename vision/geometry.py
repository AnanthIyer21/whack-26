"""Our own hand maths on MediaPipe's 21 landmarks. Pure NumPy, no model, no training.

Landmark indices: 0 wrist; thumb 1-4; index 5-8; middle 9-12; ring 13-16;
pinky 17-20 (each finger: MCP knuckle, PIP middle joint, DIP, TIP).
"""
import numpy as np

from vision import config

FINGER_NAMES = ("index", "middle", "ring", "pinky")
MCP = np.array([5, 9, 13, 17])
PIP = MCP + 1
DIP = MCP + 2
TIP = MCP + 3
KNUCKLES = MCP  # blade base = centroid of these


def normalise(pts, label):
    """Wrist at the origin, palm length (0 -> 9) = 1, left hands mirrored to look right.

    Curl angles and distance ratios don't change under this, so the grip maths
    gives the same answer either way; this is the canonical hand frame for
    debugging and future gestures.
    """
    p = np.asarray(pts, dtype=np.float32)
    p = p - p[0]
    scale = np.linalg.norm(p[9])
    if scale > 1e-9:
        p = p / scale
    if label == "Left":
        p = p * np.array([-1.0, 1.0, 1.0], dtype=np.float32)
    return p


def _bend_deg(a, b, c):
    """Bend at joint b, in degrees, vectorised over rows: 0 = straight, 90 = right angle."""
    u, v = b - a, c - b
    cos = np.sum(u * v, axis=-1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def finger_curls(world):
    """Per-finger curl 0 (straight) .. 1 (fully curled) for index, middle, ring, pinky.

    world: (21, 3) metric landmarks (rotation-agnostic, so side-on fists still work).
    Curl = mean of
      angle_curl: (bend at MCP + bend at PIP) / ANGLE_FULL_CURL_DEG
      dist_curl:  how far |tip - wrist| / |mcp - wrist| has dropped from an open hand's ~1.9
    """
    w = np.asarray(world, dtype=np.float32)
    wrist = np.broadcast_to(w[0], (4, 3))
    bend = _bend_deg(wrist, w[MCP], w[PIP]) + _bend_deg(w[MCP], w[PIP], w[DIP])
    angle_curl = np.clip(bend / config.ANGLE_FULL_CURL_DEG, 0.0, 1.0)
    ratio = np.linalg.norm(w[TIP] - w[0], axis=-1) / (np.linalg.norm(w[MCP] - w[0], axis=-1) + 1e-9)
    dist_curl = np.clip((config.DIST_OPEN_RATIO - ratio) / config.DIST_RANGE, 0.0, 1.0)
    return (angle_curl + dist_curl) / 2.0


def curl_score(world):
    """Returns (score 0..1, per-finger curls (4,), number of curled fingers)."""
    curls = finger_curls(world)
    return float(curls.mean()), curls, int(np.sum(curls >= config.FINGER_CURLED))


def raw_grip(score, n_curled):
    return score >= config.GRIP_ENTER and n_curled >= config.MIN_CURLED_FINGERS


def grip_certainty(score):
    """0 at the grip/open boundary, 1 when clearly fist or clearly open."""
    mid = (config.GRIP_ENTER + config.OPEN_BELOW) / 2.0
    half = (config.GRIP_ENTER - config.OPEN_BELOW) / 2.0
    return float(np.clip(abs(score - mid) / half, 0.0, 1.0))


# Blade modes (config.BLADE_MODE):
#   "grip"    - real sword grip (Aaron's choice): the handle runs through the curled
#               fingers, the blade runs across the fist from the pinky side and out
#               past the thumb. Base = centre of the grip.
#   "knuckle" - original spec: base at the knuckles, blade along wrist -> middle knuckle.
GRIP_POINTS = np.array([5, 9, 13, 17, 6, 10, 14, 18])   # knuckles + curled middle joints
_AXIS = {
    "grip": (np.array([17, 18]), np.array([5, 6])),       # pinky side -> index side
    "knuckle": (np.array([0]), np.array([9])),            # wrist -> middle knuckle
}


def blade_base(img, mode=None):
    """Where the blade sits in normalised mirrored image coords (x right, y down)."""
    mode = mode or config.BLADE_MODE
    idx = GRIP_POINTS if mode == "grip" else KNUCKLES
    return img[idx, :2].mean(axis=0).astype(np.float64)


def _axis(pts, mode):
    a, b = _AXIS[mode or config.BLADE_MODE]
    pts = np.asarray(pts, dtype=np.float64)
    return pts[b].mean(axis=0) - pts[a].mean(axis=0)


def blade_angle(img, width, height, mode=None):
    """Blade direction in true pixel proportions, y down.

    0 = pointing right, +pi/2 = down, -pi/2 = up.
    """
    d = _axis(img, mode)
    return float(np.arctan2(d[1] * height, d[0] * width))


def foreshortening(world, mode=None):
    """2D (image-plane) length / 3D length of the blade axis. ~1 = flat to the camera,
    ~0 = pointing straight at the camera (angle unreliable)."""
    d = _axis(world, mode)
    full = np.linalg.norm(d)
    return float(np.linalg.norm(d[:2]) / full) if full > 1e-9 else 0.0
