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
MAX_SAMPLE_GAP = 0.10          # samples further apart than this reset the blade history (no cut)
MAX_SUBSTEP_ANGLE = math.radians(15)  # big rotations are split into steps no larger than this

# Hand tracking
HAND_STALE = 0.30              # HandState older than this counts as "no hand"
PAUSE_GRACE = 0.50             # bad hand state must last this long before auto-pause

# Mouse input
MOUSE_MAX_TILT = math.radians(65)   # furthest the katana leans from upright (never upside down)
MOUSE_TILT_SPEED = 900.0       # sideways speed (px/s) that gives about 3/4 of the full lean
MOUSE_TILT_EASE = 12.0         # how quickly the blade eases to its lean (per second; higher = snappier)
MOUSE_VEL_SMOOTH = 0.05        # seconds of smoothing on mouse speed (removes jitter)
MOUSE_START_ANGLE = -math.pi / 2   # pointing straight up (screen coords, y down)

# Colours
GLOW = (225, 235, 255)          # steel-white swoosh behind the katana
