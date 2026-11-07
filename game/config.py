"""Every tunable number for the game lives here."""

WIDTH, HEIGHT = 1280, 720
FPS = 60
MAX_DT = 1 / 20          # cap for simulation time so a hitch never teleports fruit
TITLE = "WHACK 26 - Fruit Ninja vs the Rival"

# Colours (R, G, B)
BG_TOP = (28, 18, 12)
BG_BOTTOM = (62, 38, 22)
WHITE = (245, 245, 245)
GOLD = (235, 190, 70)
GREY = (140, 140, 150)
DARK = (15, 10, 8)

# --- Play ---
GRAVITY = 1400.0          # px/s^2
LIVES = 5
CUT_SPEED = 900.0         # blade tip speed (px/s) needed to cut; tune with - and = in debug
COMBO_GAP = 0.25          # max seconds between cuts in one combo
COMBO_MIN = 3             # cuts needed for a combo
STREAK_STEP = 5           # streak event every 5 cuts in a row
SAMPLE_GAP_RESET = 0.1    # if two blade samples are further apart than this, forget the old one
SHEATHE_DEBOUNCE = 0.2    # sword must stay sheathed this long before sword_sheathed is sent
COUNTDOWN_STEP = 0.8      # seconds per 3, 2, 1, SLICE!
BOMB_FREEZE = 0.4         # seconds frozen after a bomb hit
BOMB_EXPLODE = 1.2        # seconds of explosion before the game-over screen
FINAL_ROAST_WAIT = 6.0    # seconds the game-over screen waits for the rival's roast

# Difficulty ramps from 0 to 1 over this many seconds
RAMP_SECONDS = 90.0
THROW_GAP = (1.4, 0.7)    # seconds between volleys at d=0 and d=1
BOMB_CHANCE = (0.05, 0.18)
GOLDEN_CHANCE = 0.02      # per volley, only after GOLDEN_AFTER seconds
GOLDEN_AFTER = 20.0

# name: (radius, colour, points)
FRUITS = {
    "watermelon": (52, (60, 160, 60), 1),
    "orange": (36, (245, 150, 30), 1),
    "apple": (34, (200, 30, 40), 1),
    "banana": (40, (245, 220, 70), 1),
    "strawberry": (26, (230, 40, 70), 1),
}
GOLDEN = ("golden", 32, (255, 215, 0), 10)
BOMB = ("bomb", 34, (30, 30, 35), 0)
