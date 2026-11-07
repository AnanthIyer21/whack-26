# WHACK 26: Fruit Ninja vs a smug AI rival

Team spec (final, after the restart). Each person's Claude prompt is shared in the Discord.

## Overview

We're at WHACK 26, the Warwick hackathon, Sat 7 to Sun 8 Nov 2026. Our Devpost submission is due **Sun 8 Nov at 11:00 UK time**; we're aiming to submit by 10:30. We're entering the **incident.io challenge** and we want to win it. The brief: "Most AI is built to answer after the fact. You ask a question, wait, and get a response. But the world doesn't wait. Things happen in real time, and the most interesting moments are over before you could type a prompt about them. Build an agent that reacts to a live feed as it happens, with personality. Point it at a camera, microphone, screen or a game and make it respond in the moment."

**What we're building:** Fruit Ninja played with one hand through a webcam. Hold one hand up and make a fist, and a virtual sword appears in it; the blade follows the tilt of your fist, so you slash fruit by swinging it like a real sword. A smug AI rival watches you play and heckles you out loud in real time: it gloats when you miss or hit a bomb, gets nervous when you're on a streak, mocks you when you pause, and roasts your habits.

**What we build ourselves:** MediaPipe (pretrained, not ours) gives 21 points per hand. We don't train anything: grip and open are worked out from those points with our own maths (finger curl from distances and angles), plus our own smoothing, blade geometry, the game, and the rival's timing and personality. The LLM only writes the rival's big-moment lines, so this is not an AI wrapper. (Never say "trained model" in the pitch.)

**Team (4):** Aaron (vision), Pricysquirrl (game), RBadiadka7 (art and sound, the reliability check, the demo), Ananth (`shared/`, integration, testing every merge, the rival).

**Full restart:** everyone starts from a fresh Claude Code session on the final `main`. Don't reuse code from before the restart (Pricysquirrl's old game is archived on the `pricysquirrl-old` branch for reference only). Repo: github.com/AnanthIyer21/whack-26.

**Stack:** Python 3.11, one program with three threads.

- Main thread: pygame-ce game loop at 60 fps.
- Vision thread: OpenCV webcam -> MediaPipe hand landmarks -> our grip maths, stabiliser and blade geometry -> publishes HandState. (OpenCV, MediaPipe, NumPy or PyTorch tensors for the maths.)
- Rival thread: reads game events -> decides whether and what to say -> Claude API for big moments, ElevenLabs for the voice -> plays audio and sends subtitles to the game.

### Game rules

- **Play** only while exactly **one hand** is in frame and **gripping**. That hand is the sword hand.
- **The sword:** the blade starts at the fist and points along the line from the wrist to the middle knuckle, so tilting your fist tilts the blade.
- **Auto-pause:** anything else pauses the game: no hands, two hands, or the hand open or unclear. The pause screen has a **Quit** button you click with the mouse. Close your fist again to resume, with a 3-2-1 countdown.
- **Slicing:** each fruit and the blade have hitboxes; a fruit is cut when they overlap and the blade is moving fast enough.
- **Scoring:** cut fruit scores points (plus combos and streaks). A fruit that falls off the bottom uncut scores nothing.
- **Lives:** 3 lives; each bomb you hit costs one.
- **Timer:** each run lasts 60 seconds by default, adjustable in a settings screen.
- **The run ends** when the timer runs out, you lose all 3 lives, or you press Quit on the pause screen. Then the game over screen shows your score and the rival's final roast.
- **Extensions** (free-hand gesture moves, face reactions) are parked. We'll write their spec only once the core game works.

### Shared interfaces (Ananth writes these in `shared/`; don't change them without telling everyone)

1. **HandState** (vision -> game), read with `get_hand_state()`: `sword_visible` (bool); `sword_active` (bool: the sword hand is gripping); `blade_base` (x, y, each 0 to 1: where the blade leaves the fist; x mirrored like a selfie, y from top to bottom); `blade_angle` (radians, smoothed); `hands_in_frame` (int: 0, 1 or 2); `gesture` (str: "none" until extensions); `confidence` (float, 0 to 1); `t` (`time.monotonic()` of the frame). The blade length is a constant in `shared/`; the game computes the tip and the slice speed itself.
2. **events** (game -> rival): a `queue.Queue` of dicts, each with `"type"` and `"t"`. Types: `game_start`; `sword_drawn`; `sword_sheathed`; `slice` (fruit); `miss` (fruit fell off the bottom uncut, side: "left" or "right"); `combo` (n); `streak` (n); `streak_broken` (n); `bomb_hit` (costs a life); `life_lost` (lives_left); `pause` (reason: "no_hand", "two_hands" or "not_gripping"); `resume`; `time_warning` (seconds_left, e.g. 10); `game_over` (score, best_combo, duration, reason: "lives", "timer" or "quit").
3. **rival_lines** (rival -> game): a `queue.Queue` of dicts `{"text": str, "mood": "smug" | "rattled" | "defensive" | "gloating", "duration": seconds}` for the speech bubble and avatar.
4. **get_latest_frame()** (vision -> anyone): the latest camera frame, read-only, for the webcam preview. Only vision ever opens the camera.

### Repo layout

`main.py` (starts the threads), `shared/` (HandState, the queues, `get_latest_frame()`, event schema, constants such as blade length and the default timer), `vision/`, `game/`, `agent/` (the rival), `assets/` (sprites, sounds, avatar), `tools/` (debug views, latency measurement, the reliability check). Never commit video. API keys live only in `.env` (gitignored): `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

### Git workflow

**First:** Ananth writes `shared/`, a `main.py` skeleton that starts the three threads with fakes plugged in, `.gitignore`, `requirements.txt` and `.env.example`, and merges them into `staging`. Everyone pulls `staging` into their branch as soon as it lands; until then, build against your own fakes. Don't write your own `shared/`.

Work only on your own branch (`aaron`, `pricysquirrl`, `rbadiadka7`, `ananth`). Commit small and often. At each milestone, open a pull request into `staging`; we test together on `staging`; `staging` is merged into `main` only when the whole team is happy. Never push to `main`. Pull `staging` into your branch often.

### Demo laptop and keys

The demo laptop is Ananth's. It holds the only `.env` with the Claude and ElevenLabs keys (never in the group chat or in git), and Ananth tests every merge into `staging` on it.

### Team milestones (in order; no clock times)

1. `shared/` and the `main.py` skeleton on `staging`; everyone pulls it.
2. Game playable with the mouse as the sword; vision debug window shows grip and the blade; rival speaking saved lines on fake events; first art and sounds in.
3. The real sword working in the game on `staging`; auto-pause working; rival reacting to real play.
4. Full game end to end on `staging`: title, settings, timer, sword, slicing, bombs and lives, pause and Quit, rival with Claude roasts and avatar, game over.
5. Reliability check and latency numbers for the pitch; polish; extensions only if there's time.

**Fixed times:** feature freeze Sun 08:00; demo video, Devpost and two rehearsals between 08:00 and 10:30; **submit by 10:30**.

## Roles

| Who | Role | Owns |
|---|---|---|
| Aaron | Vision | MediaPipe tracking, the sword hand, grip and open from landmark maths (no training), the stabiliser, blade geometry (One Euro smoothing), `hands_in_frame`, `get_latest_frame()`, the debug view with a counter mode, latency per stage |
| Pricysquirrl | Game | pygame-ce from scratch: title, settings and timer, fruit and bombs, 3 lives, the drawn sword and trail, hitbox slicing with a speed threshold, scoring and combos, auto-pause with the Quit button and 3-2-1 resume, the rival's avatar and speech bubble on screen, events, game over |
| RBadiadka7 | Art and sound, reliability check, demo | The rival's avatar faces, game art and sounds, the live reliability check with all four of us, the numbers slide, Devpost, demo video, pitch and rehearsals |
| Ananth | `shared/`, integration, testing, rival | `shared/` and the `main.py` skeleton first (everyone waits on this), wiring the real parts together, testing every `staging` merge on his laptop (the demo laptop), then the rival: timing engine, personality, cached ElevenLabs line bank, Claude for big moments, audio, subtitles |

## What we show the judges

- Vision: latency per stage (mean and p95) and the live reliability check (how often grip and open were recognised for each of us, left and right hands).
- The rival's timing: event-to-voice latency, and lines that land at the right moment without talking over itself.
- A judge playing live.
