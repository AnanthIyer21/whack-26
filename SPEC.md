# WHACK 26: Fruit Ninja vs a smug AI rival

Team spec. Each person's Claude prompt is shared in the Discord.

## Overview

We're at WHACK 26, the Warwick hackathon, Sat 7 to Sun 8 Nov 2026. Our Devpost submission is due **Sun 8 Nov at 11:00 UK time**; we're aiming to submit by 10:30. We're entering the **incident.io challenge** and we want to win it. The brief: "Most AI is built to answer after the fact. You ask a question, wait, and get a response. But the world doesn't wait. Things happen in real time, and the most interesting moments are over before you could type a prompt about them. Build an agent that reacts to a live feed as it happens, with personality. Point it at a camera, microphone, screen or a game and make it respond in the moment."

**What we're building:** Fruit Ninja played with your hand through a webcam. Your index fingertip is the blade. A smug AI rival watches you play and heckles you out loud in real time: it gloats when you miss or hit a bomb, gets nervous when you're on a streak, and roasts your habits. Special moves are triggered by hand gestures recognised by a gesture model **we train ourselves**. This must not be an AI wrapper: the trained vision model is the core of the project.

**Team (4):** Aaron (vision lead, the only one of us who has trained CV models), Pricysquirrl (game), RBadiadka7 (data, face model, demo), Ananth (rival agent). Repo: github.com/AnanthIyer21/whack-26.

**Stack:** Python 3.11, one program with three threads.

- Main thread: pygame-ce game loop at 60 fps.
- Vision thread: OpenCV webcam -> MediaPipe hand landmarks -> our PyTorch gesture model -> publishes HandState.
- Rival thread: reads game events -> decides whether and what to say -> Claude API for big moments, ElevenLabs for the voice -> plays audio and sends subtitles to the game.

Mostly Mac laptops. Warwick DCS GPU machines are available if we need more compute, but training should be light.

### Gesture moves

- **Tier 1 (train first):** chop (slices everything on screen), fist held about 0.5 s (slows time), open palm (shield: blocks the next bomb), finger gun (shoots one fruit at range), thumbs down (taunts the rival; it gets defensive), peace sign (double points for 5 s), plus a **none** class. "None" must include fast slicing swipes, resting hands and random movement, so normal slicing never fires a move.
- **Tier 2 (only once tier 1 is above 90% on held-out data):** OK sign (pause), rock horns (rage mode: faster fruit, double points), wave (the rival shuts up for 10 s).
- **Tier 3 (last, separate logic):** two-hand clap (smash all bombs), pinch (grab and throw a fruit).

### Shared interfaces (agreed by the team; don't change them without telling everyone)

1. **HandState** (vision -> game), read with `get_hand_state()`: `x`, `y` = index fingertip, 0 to 1 (x mirrored like a selfie, y from top to bottom); `visible` (bool); `gesture` (str: "none", "chop", "fist", "palm", "finger_gun", "thumbs_down", "peace", later "ok", "horns", "wave", "clap", "pinch"); `confidence` (float, 0 to 1); `t` (`time.monotonic()` of the frame).
2. **events** (game -> rival): a `queue.Queue` of dicts, each with `"type"` and `"t"`. Types: `game_start`; `slice` (fruit); `miss` (fruit, side: "left" or "right"); `bomb_hit`; `combo` (n); `streak` (n); `streak_broken` (n); `gesture` (name); `special_move` (name, fruits_hit); `life_lost` (lives_left); `game_over` (score, best_combo, duration). Later: `face` (expression).
3. **rival_lines** (rival -> game): a `queue.Queue` of dicts `{"text": str, "mood": "smug" | "rattled" | "defensive" | "gloating", "duration": seconds}` for the speech bubble and avatar.

### Repo layout

`main.py` (starts the threads), `shared/` (HandState, event schema, constants), `vision/`, `game/`, `agent/`, `tools/` (recorder, training, evaluation), `data/` (raw recordings, gitignored), `models/` (small trained weights), `prompts/`. API keys live only in `.env` (gitignored): `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

### Git workflow

Work only on your own branch (`aaron`, `pricysquirrl`, `rbadiadka7`, `ananth`). Commit small and often. Open pull requests into `staging`; we test together on `staging`; `staging` is merged into `main` only when the whole team is happy. Never push to `main`. Pull `staging` into your branch regularly to avoid conflicts.

### Team checkpoints (UK time)

| By | Done |
|---|---|
| Sat 15:30 | Interfaces committed in `shared/`; game playable with the mouse; rival speaks cached lines from fake events; recorder works |
| Sat 18:00 | Tier 1 data recorded by all four; first gesture model trained; special-move effects in the game |
| Sat 22:00 | Everything joined up on `staging` and playable by hand; gesture model above 90% on held-out data |
| Overnight | Tier 2 moves, stretch goals, polish |
| Sun 08:00 | Feature freeze |
| Sun 08:00 to 10:30 | Demo video, Devpost, rehearse twice, submit by 10:30 |

## Roles

| Who | Role | Owns |
|---|---|---|
| Aaron | Vision lead | Webcam, MediaPipe hand tracking, the fingertip blade, the gesture model (PyTorch), evaluation (accuracy, confusion matrix, latency), `HandState`. Stretch: our own hand detector |
| Pricysquirrl | Game | pygame-ce Fruit Ninja: fruit, bombs, blade trail, slicing, juice, combos, score, lives, special-move effects, HUD, the rival's avatar and speech bubble, screens, events |
| RBadiadka7 | Data, face model, demo | Recorder tool, recording sessions with all four of us, data checks. Stretch: face-reaction model. Devpost, demo video, pitch and rehearsals |
| Ananth | Rival agent | Timing engine (when to speak), personality, cached ElevenLabs line bank, Claude for big moments, audio, subtitles |

## Pitch proof (what shows it isn't an AI wrapper)

- A confusion matrix and held-out accuracy for the gesture model (trained on three people, tested on the fourth).
- End-to-end latency: camera frame to gesture, and game event to the rival's voice.
- A live demo with a judge playing.
