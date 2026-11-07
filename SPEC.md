# WHACK 26: Fruit Ninja vs a smug AI rival

Team spec. Each person's Claude prompt is shared in the Discord.

## Overview

We're at WHACK 26, the Warwick hackathon, Sat 7 to Sun 8 Nov 2026. Our Devpost submission is due **Sun 8 Nov at 11:00 UK time**; we're aiming to submit by 10:30. We're entering the **incident.io challenge** and we want to win it. The brief: "Most AI is built to answer after the fact. You ask a question, wait, and get a response. But the world doesn't wait. Things happen in real time, and the most interesting moments are over before you could type a prompt about them. Build an agent that reacts to a live feed as it happens, with personality. Point it at a camera, microphone, screen or a game and make it respond in the moment."

**What we're building:** Fruit Ninja played with your hands through a webcam. You pick your sword hand at the start; when you make a fist with it, a virtual sword appears in your hand, and the blade follows the tilt of your fist, so you slash fruit by swinging it like a real sword. Open your hand and the sword disappears. A smug AI rival watches you play and heckles you out loud in real time: it gloats when you miss or hit a bomb, gets nervous when you're on a streak, and roasts your habits.

**No model training.** MediaPipe already detects 21 points on each hand in real time, so we don't train a hand detector or a classifier. Our own work is the real-time pipeline on top: hand-pose logic, smoothing, the blade physics, the game, and the rival's timing and personality. The LLM is only used for the rival's big-moment lines, so this is not an AI wrapper. (Fallback only if a rule proves unreliable, for example palm up: a tiny classifier on landmarks.)

**Team (4):** Aaron (vision), Pricysquirrl (game), RBadiadka7 (look, sound, testing and demo), Ananth (`shared/`, integration and the rival). Repo: github.com/AnanthIyer21/whack-26.

**Stack:** Python 3.11, one program with three threads.

- Main thread: pygame-ce game loop at 60 fps.
- Vision thread: OpenCV webcam -> MediaPipe hand landmarks -> our pose logic and smoothing -> publishes HandState.
- Rival thread: reads game events -> decides whether and what to say -> Claude API for big moments, ElevenLabs for the voice -> plays audio and sends subtitles to the game.

Mostly Mac laptops.

### Controls

- **Sword hand:** picked on the title screen (left or right) and fixed for the game. The other hand stays behind your back in the first version.
- **Grip (fist) on the sword hand:** the sword appears. The blade starts at the fist and points along the line from the wrist through the knuckles, so tilting your fist tilts the sword. **Open hand:** the sword disappears.
- **Slicing:** a fruit is cut when the blade sweeps through it fast enough between frames.
- **Pause:** open both hands with palms facing up and hold briefly. The game pauses (how to resume is for the game and vision sessions to agree).
- **Game over:** hitting a bomb with the sword ends the game.

### How vision works (rules on MediaPipe landmarks)

- **Grip vs open:** fingers curled (fingertips closer to the wrist than their middle joints) means grip; fingers extended means open. Use hysteresis so the sword never flickers.
- **Palm up:** open hand with the palm facing up, worked out from the palm's orientation (for example the direction of a vector perpendicular to the wrist, index-knuckle and pinky-knuckle points, taking handedness into account). This is the hardest rule, so test it on all four of us early.
- **Blade:** base at the fist, angle from wrist to middle knuckle, both smoothed (for example a One Euro filter).
- **Extension 1 (once the core game works):** the free hand comes out from behind your back for gesture moves, detected the same way from which fingers are extended: chop (slices everything), open palm to the camera (shield: blocks the next bomb), finger gun (shoots one fruit), thumbs down (taunts the rival), peace sign (double points for 5 s), OK sign (slows time).
- **Extension 2:** rock horns (rage mode), wave (the rival shuts up for 10 s), clap, pinch.

### Shared interfaces (Ananth writes these in `shared/`; don't change them without telling everyone)

1. **HandState** (vision -> game), read with `get_hand_state()`: `sword_hand` ("left" or "right"); `sword_visible` (bool); `sword_active` (bool: the sword hand is gripping); `blade_base` (x, y, each 0 to 1: where the blade leaves the fist; x mirrored like a selfie, y from top to bottom); `blade_angle` (radians, smoothed); `pause_pose` (bool: both hands open, palms up, held long enough); `gesture` (str: free-hand move, "none" until extension 1); `t` (`time.monotonic()` of the frame). The blade length is a constant in `shared/`, so the game computes the tip.
2. **events** (game -> rival): a `queue.Queue` of dicts, each with `"type"` and `"t"`. Types: `game_start`; `sword_drawn`; `sword_sheathed`; `slice` (fruit); `miss` (fruit, side: "left" or "right"); `combo` (n); `streak` (n); `streak_broken` (n); `life_lost` (lives_left); `pause`; `resume`; `bomb_hit` (always followed by `game_over`); `game_over` (score, best_combo, duration, reason). Extension: `gesture` (name), `special_move` (name, fruits_hit), `face` (expression).
3. **rival_lines** (rival -> game): a `queue.Queue` of dicts `{"text": str, "mood": "smug" | "rattled" | "defensive" | "gloating", "duration": seconds}` for the speech bubble and avatar.
4. **set_sword_hand("left" | "right")** (game -> vision): the title screen calls this so vision knows which hand to follow.
5. **get_latest_frame()** (vision -> anyone): the latest camera frame, read-only, for the face reactions and the webcam preview. Only vision ever opens the camera.

### Repo layout

`main.py` (starts the threads), `shared/` (HandState, the queues, `set_sword_hand()`, `get_latest_frame()`, event schema, constants), `vision/`, `game/`, `agent/`, `assets/` (sprites, sounds, avatar), `tools/` (debug and test scripts). API keys live only in `.env` (gitignored): `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

### Git workflow

**Before anyone builds on the interfaces:** Ananth writes `shared/`, a `main.py` skeleton that starts the three threads with fakes plugged in, `.gitignore`, `requirements.txt` and `.env.example`, and merges them into `staging` by 15:00. Everyone pulls `staging` into their branch as soon as it lands; until then, build against your own fakes.

Work only on your own branch (`aaron`, `pricysquirrl`, `rbadiadka7`, `ananth`). Commit small and often. Open pull requests into `staging`; we test together on `staging`; `staging` is merged into `main` only when the whole team is happy. Never push to `main`. Pull `staging` into your branch regularly to avoid conflicts.

### Demo laptop and keys

Pick one demo laptop now (the one with the best webcam). It holds the only `.env` with the Claude and ElevenLabs keys; share keys by private message, never in the group chat or in git.

### Team checkpoints (UK time)

| By | Done |
|---|---|
| Sat 15:00 | Ananth's `shared/` and `main.py` skeleton merged into `staging`; everyone pulls it |
| Sat 16:00 | Game playable with the mouse as the sword; vision debug window shows both hands, grip and the blade; rival speaks cached lines from fake events |
| Sat 18:30 | The real sword working in the game on `staging`; pause pose working; rival reacting to real game events |
| Sat 22:00 | Full game end to end on `staging`: title, sword, slicing, bombs, pause, rival with Claude roasts and avatar |
| Overnight | Extension 1 gestures, face reactions, juice and polish |
| Sun 08:00 | Feature freeze |
| Sun 08:00 to 10:30 | Demo video, Devpost, rehearse twice, submit by 10:30 |

## Roles

| Who | Role | Owns |
|---|---|---|
| Aaron | Vision | MediaPipe tracking of both hands, locking onto the sword hand, grip and open rules, the blade (position and angle, smoothed), the pause pose, `get_latest_frame()`, the debug view, latency and reliability numbers. Extension: free-hand gesture moves |
| Pricysquirrl | Game | pygame-ce Fruit Ninja: title screen with sword-hand choice, fruit, bombs that end the game, the drawn sword and its trail, swept-blade slicing, juice, combos, score, lives, pause screen, HUD, the rival's avatar and speech bubble, events. Extension: move effects |
| RBadiadka7 | Look, sound, testing, demo | The rival's avatar faces, game art and sounds, testing every `staging` merge on the demo laptop. Stretch: face reactions from MediaPipe blendshapes. Devpost, demo video, pitch and rehearsals |
| Ananth | `shared/`, integration, rival | `shared/` and the `main.py` skeleton first, wiring the threads together, then the rival: timing engine, personality, cached ElevenLabs line bank, Claude for big moments, audio, subtitles |

## Pitch proof

- Vision latency (camera frame to sword on screen) and how reliably grip, open and palm up are recognised across all four of us.
- The rival's timing: event-to-voice latency, and lines that land at the right moment without talking over itself.
- A live demo with a judge playing.
