"""All vision tunables in one place. Change numbers here, not in the code.

Thresholds marked (calibrate) are starting values; we tune them on real hands
with the debug window's sliders, then write the final numbers back here.
"""
from pathlib import Path

# ---- Camera ---------------------------------------------------------------
CAMERA_INDEX = 0          # built-in webcam; try 1 if an external cam is plugged in
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30
USE_DSHOW = True          # DirectShow on Windows: opens fast and honours MJPG
USE_MJPG = True

# ---- MediaPipe ------------------------------------------------------------
MODEL_PATH = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"
MAX_HANDS = 2
MIN_DETECTION_CONF = 0.5
MIN_PRESENCE_CONF = 0.5
MIN_TRACKING_CONF = 0.5
# MediaPipe's handedness assumes a mirrored (selfie) image. We feed it a
# mirrored image, so in theory no flip is needed. Verified with
# tools/camera_check.py: set True only if your right hand shows as "Left".
FLIP_HANDEDNESS = False
# Two detections whose wrists are closer than this (normalised units) are the
# same hand detected twice.
DEDUPE_WRIST_DIST = 0.05

# ---- Grip maths (calibrate) ----------------------------------------------
# angle_curl = (MCP bend + PIP bend) / ANGLE_FULL_CURL_DEG
ANGLE_FULL_CURL_DEG = 160.0
# dist ratio r = |tip - wrist| / |mcp - wrist|; r >= DIST_OPEN_RATIO -> 0 curl,
# r <= DIST_OPEN_RATIO - DIST_RANGE -> full curl
DIST_OPEN_RATIO = 1.9
DIST_RANGE = 0.9
FINGER_CURLED = 0.6       # a finger counts as curled at or above this
MIN_CURLED_FINGERS = 3    # of index, middle, ring, pinky

# ---- Stabiliser (hysteresis) ---------------------------------------------
GRIP_ENTER = 0.60         # score must be >= this (and enough fingers curled)
GRIP_ENTER_FRAMES = 2
GRIP_EXIT = 0.40          # leave GRIP when score <= this ...
GRIP_EXIT_FRAMES = 3      # ... for this many frames in a row
OPEN_BELOW = 0.30         # outside GRIP: <= this is OPEN, otherwise UNCLEAR

# ---- Hand-count grace ----------------------------------------------------
LOST_GRACE_S = 0.150      # hold the last state this long after the hand vanishes
TWO_HANDS_FRAMES = 3      # second hand must be seen this many frames in a row

# ---- One Euro filters ----------------------------------------------------
POS_MIN_CUTOFF = 1.0
POS_BETA = 3.0
POS_D_CUTOFF = 1.0
ANG_MIN_CUTOFF = 1.0
ANG_BETA = 0.5
ANG_D_CUTOFF = 1.0
# Side-on hold: if the wrist->middle-knuckle line's 2D length / 3D length is
# below this, the angle is unreliable, so we hold the last good angle.
SIDE_ON_RATIO = 0.5
SIDE_ON_BLEND_S = 0.15    # time to blend back once the angle is reliable again
