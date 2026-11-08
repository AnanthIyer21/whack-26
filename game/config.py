"""Every tunable number for the game lives here, so we can tweak without hunting."""
import math

# Window and loop
W, H = 1280, 720          # logical resolution; pygame scales it to the window
FPS = 60
MAX_DT = 0.05             # physics never steps more than 50 ms at once (stalls don't teleport fruit)

# Sword
BLADE_LENGTH_FALLBACK = 0.30   # fraction of screen height; the real value comes from shared/
DRAW_TIME = 0.15               # seconds for the blade to grow out of the fist
TRAIL_TIME = 0.12              # seconds of swept ribbon kept behind the blade
CUT_SPEED = 1.2                # tip speed needed to cut, in screen heights per second
MAX_SAMPLE_GAP = 0.10          # normal gap between tracking samples; longer = a lag spike / dropout
MAX_BRIDGE_GAP = 0.45          # lag spikes and short dropouts up to this long are BRIDGED: the blade
                               # is swept along the straight path, so fruit in between still get cut
MAX_BRIDGE_DIST = 0.8          # ...unless the fist "jumped" further than this (fraction of width):
                               # that's a tracking glitch, not a swing
MAX_SUBSTEP_ANGLE = math.radians(15)  # big rotations are split into steps no larger than this

# Hand tracking
HAND_STALE = 0.30              # HandState older than this counts as "no hand"
# Swing prediction through tracking dropouts (game/predict.py)
PREDICT_MAX = 0.35             # keep the blade flying this long after the last real detection
                               # (then it hovers, still armed, until MAX_BRIDGE_GAP)
PREDICT_DAMPING = 2.5          # how fast a predicted swing slows down (per second)
PREDICT_MIN_SPEED = 0.4        # only predict if the fist was moving this fast (screen heights/s)
PREDICT_MIN_SPIN = 4.0         # ...or the blade was turning this fast (radians/s)
PREDICT_VEL_WINDOW = 0.12      # measure the swing over this much recent tracking
GLIDE_TIME = 0.08              # when the hand is found again, glide to it over this long
GLIDE_MIN_DIST = 25            # (px) smaller corrections just snap
# Room for error on "lag sweeps" (bridged gaps, predicted swings, gliding back): the path is a
# best guess, so be generous to the player
LAG_HIT_PAD = 45               # px added to every fruit's hitbox
LAG_SPEED_FACTOR = 0.6         # cut at 60% of the normal speed bar
LAG_BOMB_FACTOR = 0.6          # bombs shrink to 60%: a guessed path shouldn't blow you up
PAUSE_GRACE = 0.50             # bad hand state must last this long before auto-pause
START_COUNTDOWN = 1.5          # 3-2-1 before a run (0.5 s per number)
RESUME_HOLD = 0.5              # after a pause: hold your fist this long (a ring fills round the katana)
COUNTDOWN_NUMBERS = 3

# Mouse input
MOUSE_MAX_TILT = math.radians(55)   # furthest the katana leans from upright (never upside down)
MOUSE_TILT_SPEED = 1500.0      # sideways speed (px/s) that gives about 3/4 of the full lean
MOUSE_TILT_EASE = 7.0          # how quickly the blade eases to its lean (per second; higher = snappier)
MOUSE_FOLLOW = 28.0            # how quickly the katana follows the cursor (per second; a touch of weight)
MOUSE_VEL_SMOOTH = 0.05        # seconds of smoothing on mouse speed (removes jitter)
MOUSE_START_ANGLE = -math.pi / 2   # pointing straight up (screen coords, y down)

# Colours
GLOW = (225, 235, 255)          # steel-white swoosh behind the katana

# Titles (placeholder names, change freely)
TITLE = "KATANA vs GRIP-9000"
SUBTITLE = "one hand, one blade, one very smug AI"
