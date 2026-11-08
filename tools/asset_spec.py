"""Single source of truth for every asset file the game loads.

assets/MANIFEST.md describes the same contract in words for Pricysquirrl;
tools/check_assets.py validates assets/ against the tables below.
Change both together (and tell Pricysquirrl).
"""

FRUITS = ["apple", "orange", "watermelon", "banana", "strawberry"]
MOODS = ["smug", "rattled", "defensive", "gloating"]

SCALE = 4  # pixel art is drawn at 1/4 size and saved scaled x4 (nearest-neighbour)

# Sword canvas: points right, pivot = where the blade leaves the fist.
SWORD_SIZE = (288, 64)
SWORD_PIVOT = (16, 32)

# path (relative to assets/) -> (width, height); every image is RGBA PNG.
IMAGES: dict[str, tuple[int, int]] = {}
for f in FRUITS:
    IMAGES[f"fruit_{f}.png"] = (96, 96)
    IMAGES[f"fruit_{f}_half_l.png"] = (96, 96)
    IMAGES[f"fruit_{f}_half_r.png"] = (96, 96)
    IMAGES[f"splat_{f}.png"] = (128, 128)
IMAGES["bomb.png"] = (96, 96)
for i in range(6):
    IMAGES[f"explosion_{i}.png"] = (192, 192)
IMAGES["sword.png"] = SWORD_SIZE
IMAGES["sword_glow.png"] = SWORD_SIZE
IMAGES["life_full.png"] = (48, 48)
IMAGES["life_empty.png"] = (48, 48)
for m in MOODS:
    IMAGES[f"rival_{m}.png"] = (256, 256)
    IMAGES[f"rival_{m}_talk.png"] = (256, 256)
IMAGES["bubble.png"] = (48, 48)        # 9-slice, 16 px corners
IMAGES["bubble_tail.png"] = (32, 32)
IMAGES["bg_game.png"] = (1280, 720)
IMAGES["bg_title.png"] = (1280, 720)

# Milestone 2 items: reported as "pending" (warning) rather than errors during M1.
M2_IMAGES = {p for p in IMAGES if p.startswith(("splat_", "explosion_", "life_"))}

SOUNDS = [
    "sounds/sfx_slice_1.ogg", "sounds/sfx_slice_2.ogg", "sounds/sfx_slice_3.ogg",
    "sounds/sfx_whoosh_1.ogg", "sounds/sfx_whoosh_2.ogg",
    "sounds/sfx_splat.ogg", "sounds/sfx_explosion.ogg",
    "sounds/sfx_countdown_beep.ogg", "sounds/sfx_countdown_go.ogg",
    "sounds/sfx_sword_draw.ogg", "sounds/sfx_sword_sheathe.ogg",
    "sounds/sfx_combo.ogg", "sounds/sfx_streak.ogg", "sounds/sfx_game_over.ogg",
    "sounds/music_menu.ogg", "sounds/music_game.ogg",
]
M2_SOUNDS = {"sounds/music_menu.ogg", "sounds/music_game.ogg",
             "sounds/sfx_combo.ogg", "sounds/sfx_streak.ogg", "sounds/sfx_game_over.ogg"}

OTHER = ["palette.json", "CREDITS.md", "fonts/PressStart2P-Regular.ttf"]
M2_OTHER = {"fonts/PressStart2P-Regular.ttf"}
