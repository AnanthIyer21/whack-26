"""Constants shared by every part. Change only after telling the team."""

import math

# --- Blade geometry ---
# BLADE_LENGTH is a fraction of the SCREEN HEIGHT. The game multiplies it by the
# screen height in pixels for both axes, so the blade is never stretched.
# Angle convention (screen pixels, y points down):
#   tip_x = base_x + L * cos(blade_angle)
#   tip_y = base_y + L * sin(blade_angle)
# so blade_angle = 0 points right and -pi/2 points straight up.
BLADE_LENGTH = 0.25
BLADE_UP = -math.pi / 2

# --- Game rules ---
DEFAULT_RUN_SECONDS = 60
LIVES = 3
TIME_WARNING_SECONDS = 10
RESUME_COUNTDOWN = 3
FPS = 60

# --- Audio ---
# The game must call, before pygame.init():
#   pygame.mixer.pre_init(MIXER_FREQ, MIXER_SIZE, MIXER_CHANNELS, MIXER_BUFFER)
# and after init:
#   pygame.mixer.set_reserved(1)   # channel 0 is the rival's voice
MIXER_FREQ = 44100
MIXER_SIZE = -16
MIXER_CHANNELS = 2
MIXER_BUFFER = 512
VOICE_CHANNEL = 0
# While shared.rival_speaking is set, the game multiplies its own volumes by this.
DUCK_LEVEL = 0.35

# --- Rival moods (for the speech bubble and avatar) ---
MOODS = ("smug", "rattled", "defensive", "gloating")
