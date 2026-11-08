"""All face-extension tunables in one place. Change numbers here, not in the code.

Signals are MediaPipe blendshape scores (0..1), smoothed; head pose is in degrees,
relative to the player's own usual head position.
"""

from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_landmarker.task"

# ---- Loop -------------------------------------------------------------------
RATE_HZ = 10
DETECT_WIDTH = 640          # frames are downscaled to this width before detection
MAX_FACES = 3               # detect a few, but only ever read the player's (largest) face
AMBIGUOUS_RATIO = 0.75      # if face 2's area >= 75% of face 1's (sizes within 25%): no player face
FIST_MARGIN = 0.0           # skip frames where the fist (blade base) is inside the face box itself
                            # (was 15%: swinging at chin height counted as covered 20% of play)
FACE_LOST_RESET = 3.0       # face gone this long: new player, so recalibrate

# ---- Calibration --------------------------------------------------------------
BASELINE_WINDOW = 20.0      # seconds of history for the player's baseline
BASELINE_PERCENTILE = 20    # expression baseline = 20th percentile (their "resting" face)
WARMUP = 5.0                # no face events until the baseline has this much data
SMOOTHING = 0.3             # EMA factor per frame (at 10 Hz)
RELEASE_GAP = 0.08          # an expression re-arms only after dropping this far below its threshold
                            # (for head pose this is 8 degrees)
HOLD_SLACK = 0.05           # a hold keeps counting while the level hovers within this of its threshold
                            # (in-play expressions hover right on the line; a dip mustn't restart the hold)
MAX_PAUSE = 1.0             # unreadable frames (fist over face) pause the hold; longer than this resets it

# ---- Expressions ------------------------------------------------------------
# Switch any misfiring expression off here (one edit, nothing else changes).
ENABLED_EXPRESSIONS = ("smiling", "laughing", "shock", "frowning", "looking_away")

# Highest priority first: if several are held at once, only the first fires.
PRIORITY = ("laughing", "shock", "smiling", "frowning", "looking_away")

HOLD = {                    # seconds an expression must be held before it fires
    "laughing": 0.5,
    "smiling": 0.6,
    "shock": 0.4,
    "frowning": 0.7,
    "looking_away": 0.8,
}

# Tuned for IN-PLAY faces (playtest: expressions while playing peaked at only +0.03..0.11 over the old thresholds).
SMILE_MIN = 0.35            # smiling: smile >= this ...
SMILE_MARGIN = 0.15         # ... and >= baseline + this
LAUGH_SMILE = 0.35          # laughing: smile >= this (and >= baseline + LAUGH_SMILE_MARGIN)
LAUGH_JAW = 0.25            # ... and jaw >= this (and >= baseline + LAUGH_JAW_MARGIN)
LAUGH_SMILE_MARGIN = 0.10   # per-player margins so a naturally smiley face TALKING isn't "laughing"
LAUGH_JAW_MARGIN = 0.15
SHOCK_JAW = 0.40            # shock: jaw >= this, and >= baseline + SHOCK_MARGIN, and smile < SHOCK_MAX_SMILE
SHOCK_MARGIN = 0.20
SHOCK_MAX_SMILE = 0.30
FROWN_BROW = 0.35           # frowning: (brow >= this and >= baseline + FROWN_BROW_MARGIN) or mouth frown >= FROWN_MOUTH
FROWN_BROW_MARGIN = 0.15
FROWN_MOUTH = 0.30
FROWN_MAX_SMILE = 0.20      # ... and smile < this
AWAY_YAW = 25.0             # looking away: head turned > 25 deg, or tilted > 20 deg (up or down), vs usual
AWAY_PITCH = 20.0
