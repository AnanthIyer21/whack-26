# Asset contract (RBadiadka7 → Pricysquirrl)

**Status: PROPOSED. Pricysquirrl, please reply OK or ask for changes.**
The machine-readable version is `tools/asset_spec.py`; `python tools/check_assets.py` checks the folder against it.

## General
- Assumed window: **1280×720**. Tell me if the game uses a different size; backgrounds are the only thing that depends on it.
- All images are **RGBA PNG**, already at final size. Pixel art is drawn at ¼ size and scaled ×4 with nearest-neighbour, so **just blit them; don't smooth-scale them**. If you must scale, use `pygame.transform.scale` (nearest), not `smoothscale`.
- Names are lowercase snake_case. Everything lives under `assets/`.
- Colours (trail, mood accents, UI) are in `assets/palette.json`.

## Images
| What | File(s) | Size | How to use |
|---|---|---|---|
| Fruit (5) | `fruit_{apple,orange,watermelon,banana,strawberry}.png` | 96×96 | Centred on the fruit position. Hitbox suggestion: circle r = 40 |
| Halves | `fruit_<name>_half_l.png`, `fruit_<name>_half_r.png` | 96×96 | Same canvas as the whole fruit; place both at the fruit's position, then rotate them to the slice angle and fling them apart |
| Juice splat | `splat_<name>.png` | 128×128 | Draw under the fruit layer and fade out over about 1 s *(M2)* |
| Bomb | `bomb.png` | 96×96 | Hitbox suggestion: circle r = 36 |
| Explosion | `explosion_0.png` … `explosion_5.png` | 192×192 | About 60 ms per frame, centred on the bomb *(M2)* |
| Sword | `sword.png` | 288×64 | Points **right** (angle 0). **Pivot (16, 32)** = where the blade leaves the fist = `blade_base`. Scale the length to the blade-length constant, then rotate by `blade_angle` around the pivot |
| Sword glow | `sword_glow.png` | 288×64 | Same canvas and pivot as `sword.png`. Draw first with `special_flags=pygame.BLEND_ADD` |
| Slash trail | (no image) | | Drawn in code: a fading polyline of recent tip positions, colour `palette.json → trail` |
| Lives | `life_full.png`, `life_empty.png` | 48×48 | HUD, 3 in a row *(M2)* |
| Rival faces | `rival_{smug,rattled,defensive,gloating}.png` | 256×256 | Mouth closed. `mood` comes from `rival_lines` |
| Rival talking | `rival_<mood>_talk.png` | 256×256 | Mouth open; alternate with the closed frame every ~120 ms while a line is showing |
| Speech bubble | `bubble.png` | 48×48 | **9-slice**: 16 px corners, stretch the edges and centre to fit the text |
| Bubble tail | `bubble_tail.png` | 32×32 | Points down-left, towards the avatar; attach to the bubble's bottom edge |
| Backgrounds | `bg_game.png`, `bg_title.png` | 1280×720 | Pause and game over reuse these with a dark overlay drawn in code |
| Font | `fonts/PressStart2P-Regular.ttf` | | OFL licence. Score, timer, subtitles, bubble text *(M2)* |

## Sounds (`assets/sounds/`, all `.ogg`)
| Event | File |
|---|---|
| fruit cut | `sfx_slice_1.ogg`, `sfx_slice_2.ogg`, `sfx_slice_3.ogg`: metallic movie-style slash (pick one at random) |
| fast swing starts | `sfx_whoosh_1.ogg`, `sfx_whoosh_2.ogg` |
| (unused for now) | `sfx_splat.ogg`: dropped from slices, kept in case we want it back |
| bomb hit | `sfx_explosion.ogg`: on the visual boom (after `boom.WINDUP`), full volume, never ducked |
| 3, 2, 1 | `sfx_countdown_beep.ogg` |
| GO | `sfx_countdown_go.ogg` |
| `sword_drawn` | `sfx_sword_draw.ogg` |
| `sword_sheathed` | `sfx_sword_sheathe.ogg` |
| `combo` / `streak` | `sfx_combo.ogg` / `sfx_streak.ogg` *(M2)* |
| game over | `sfx_game_over.ogg` *(M2)* |
| title / settings / game over | `music_menu.ogg` (loop) *(M2)* |
| during play | `music_game.ogg` (loop) *(M2)* |

**Volume:** the rival's voice must stay audible. Implemented in `game/sfx.py`: music 0.22, SFX 0.7, explosion 1.0; everything except the explosion is multiplied by `shared.DUCK_LEVEL` while `shared.rival_speaking` is set.

## Credits
Every file's source and licence is listed in `assets/CREDITS.md`.
