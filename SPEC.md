# WHACK 26: Fruit Ninja vs a smug AI rival

Team spec. Each person's Claude prompt is shared in the Discord.

## Overview

We're at WHACK 26, the Warwick hackathon, Sat 7 to Sun 8 Nov 2026. Our Devpost submission is due **Sun 8 Nov at 11:00 UK time**; we're aiming to submit by 10:30. We're entering the **incident.io challenge** and we want to win it. The brief: "Most AI is built to answer after the fact. You ask a question, wait, and get a response. But the world doesn't wait. Things happen in real time, and the most interesting moments are over before you could type a prompt about them. Build an agent that reacts to a live feed as it happens, with personality. Point it at a camera, microphone, screen or a game and make it respond in the moment."

**What we're building:** Fruit Ninja played with your hands through a webcam. You pick your sword hand at the start; when you make a fist with it, a virtual sword appears in your hand, and the blade follows the tilt of your fist, so you slash fruit by swinging it like a real sword. Open your hand and the sword disappears. A smug AI rival watches you play and heckles you out loud in real time: it gloats when you miss or hit a bomb, gets nervous when you're on a streak, and roasts your habits. The hand states (grip, open, both palms up) are recognised by a model **we train ourselves**, and free-hand gesture moves come as the first extension. This must not be an AI wrapper: the trained vision model is the core of the project.

**Team (4):** Aaron (vision lead, the only one of us who has trained CV models), Pricysquirrl (game), RBadiadka7 (data, face model, demo), Ananth (rival agent). Repo: github.com/AnanthIyer21/whack-26.

**Stack:** Python 3.11, one program with three threads.

- Main thread: pygame-ce game loop at 60 fps.
- Vision thread: OpenCV webcam -> MediaPipe hand landmarks -> our PyTorch gesture model -> publishes HandState.
- Rival thread: reads game events -> decides whether and what to say -> Claude API for big moments, ElevenLabs for the voice -> plays audio and sends subtitles to the game.

Mostly Mac laptops. Warwick DCS GPU machines are available if we need more compute, but training should be light.

### Controls

- **Sword hand:** picked on the title screen (left or right) and fixed for the game. The other hand stays behind your back in the first version.
- **Grip (fist) on the sword hand:** the sword appears. The blade starts at the fist and points along the line from the wrist through the knuckles, so tilting your fist tilts the sword. **Open hand:** the sword disappears.
- **Slicing:** a fruit is cut when the blade sweeps through it fast enough between frames.
- **Pause:** open both hands with palms facing up and hold briefly. The game pauses (how to resume is for the game and vision sessions to agree).
- **Game over:** hitting a bomb with the sword ends the game.

### What the model recognises

- **First version (must ship):** per hand: grip, open, palm up, plus an "other" class for transitions and half-formed shapes. Palm up seen from a webcam is foreshortened and easy to confuse with an open hand, which is exactly why we train a model instead of hand-coding rules.
- **Extension 1 (free-hand gesture moves, once the first version is solid):** the free hand comes out from behind your back to trigger moves, for example chop (slices everything on screen), open palm to the camera (shield: blocks the next bomb), finger gun (shoots one fruit at range), thumbs down (taunts the rival; it gets defensive), peace sign (double points for 5 s), OK sign (slows time). Record a little data for these early if there's time, because recording with all four of us is the bottleneck.
- **Extension 2:** rock horns (rage mode), wave (the rival shuts up for 10 s), clap, pinch.

### Shared interfaces (agreed by the team; don't change them without telling everyone)

1. **HandState** (vision -> game), read with `get_hand_state()`: `sword_hand` ("left" or "right", set from the title screen); `sword_visible` (bool); `sword_active` (bool: the sword hand is gripping); `blade_base` (x, y, each 0 to 1: where the blade leaves the fist; x mirrored like a selfie, y from top to bottom); `blade_angle` (radians, from the wrist-to-knuckles direction, smoothed); `pause_pose` (bool: both hands open, palms up, held long enough); `gesture` (str: free-hand move, "none" until extension 1); `confidence` (float, 0 to 1); `t` (`time.monotonic()` of the frame). The blade length is a game constant in `shared/`, so the game computes the tip.
2. **events** (game -> rival): a `queue.Queue` of dicts, each with `"type"` and `"t"`. Types: `game_start`; `sword_drawn`; `sword_sheathed`; `slice` (fruit); `miss` (fruit, side: "left" or "right"); `combo` (n); `streak` (n); `streak_broken` (n); `life_lost` (lives_left); `pause`; `resume`; `bomb_hit` (always followed by `game_over`); `game_over` (score, best_combo, duration, reason). Extension: `gesture` (name), `special_move` (name, fruits_hit), `face` (expression).
3. **rival_lines** (rival -> game): a `queue.Queue` of dicts `{"text": str, "mood": "smug" | "rattled" | "defensive" | "gloating", "duration": seconds}` for the speech bubble and avatar.

### Repo layout

`main.py` (starts the threads), `shared/` (HandState, event schema, constants), `vision/`, `game/`, `agent/`, `tools/` (recorder, training, evaluation), `data/` (raw recordings, gitignored), `models/` (small trained weights), `prompts/`. API keys live only in `.env` (gitignored): `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

### Git workflow

Work only on your own branch (`aaron`, `pricysquirrl`, `rbadiadka7`, `ananth`). Commit small and often. Open pull requests into `staging`; we test together on `staging`; `staging` is merged into `main` only when the whole team is happy. Never push to `main`. Pull `staging` into your branch regularly to avoid conflicts.

### Team checkpoints (UK time)

| By | Done |
|---|---|
| Sat 15:30 | Interfaces committed in `shared/`; game playable with the mouse as the sword; rival speaks cached lines from fake events; recorder works |
| Sat 18:00 | Grip, open, palm up and other recorded by all four; first model trained; blade from hand tilt working in the vision debug view |
| Sat 22:00 | Everything joined up on `staging` and playable with the sword; pause pose working; model above 90% on held-out data |
| Overnight | Extension 1 gesture moves, stretch goals, polish |
| Sun 08:00 | Feature freeze |
| Sun 08:00 to 10:30 | Demo video, Devpost, rehearse twice, submit by 10:30 |

## Roles

| Who | Role | Owns |
|---|---|---|
| Aaron | Vision lead | Webcam, MediaPipe tracking of both hands, locking onto the sword hand, the sword (blade position and angle from hand tilt), the hand-state model (grip, open, palm up, other), the pause pose, evaluation (accuracy, confusion matrix, latency), `HandState`. Extension: free-hand gesture moves. Stretch: our own hand detector |
| Pricysquirrl | Game | pygame-ce Fruit Ninja: title screen with sword-hand choice, fruit, bombs that end the game, the drawn sword and its trail, swept-blade slicing, juice, combos, score, lives, pause screen, HUD, the rival's avatar and speech bubble, events. Extension: move effects |
| RBadiadka7 | Data, face model, demo | Recorder tool, recording sessions with all four of us, data checks. Stretch: face-reaction model. Devpost, demo video, pitch and rehearsals |
| Ananth | Rival agent | Timing engine (when to speak), personality, cached ElevenLabs line bank, Claude for big moments, audio, subtitles |

## Pitch proof (what shows it isn't an AI wrapper)

- A confusion matrix and held-out accuracy for the hand-state model (trained on three people, tested on the fourth), especially open versus palm up.
- End-to-end latency: camera frame to sword on screen, and game event to the rival's voice.
- A live demo with a judge playing.
