# Pitch (2:30) and live demo flow

> Owner: RBadiadka7. Roles are decided at rehearsal 1; defaults below. Times are cumulative.
> Words in **bold** are cues for the player. Never say "trained model".

## Roles (default)
| Who | Job |
|---|---|
| Aaron | Plays (knows the grip best) |
| RBadiadka7 | Narrates, drives the slide |
| Ananth | At the laptop: start/restart, audio, fallbacks |
| Pricysquirrl | Q&A on the game; holds the phone hotspot |

## Script

**0:00 to 0:15, hook** (game already on the title screen, GRIP-9000 visible)
> "Most AI waits for you to type a question. Ours doesn't wait. It watches you, and it's rude about it.
> Meet GRIP-9000."
*(Aaron starts the run: **make a fist** → 3-2-1 → GO. GRIP-9000's intro line plays.)*

**0:15 to 1:30, live play** (narrator talks only in the gaps, never over GRIP-9000)
1. **Draw the sword**: "Make a fist and a sword appears. The blade follows the tilt of your fist."
2. **Slash a few fruit**, then **a fast multi-cut**: combo; GRIP-9000 gets rattled.
3. **Hit a bomb on purpose**: explosion, GRIP-9000 cackles.
4. **Open the hand**: game freezes instantly. "Open your hand, drop it, or bring in a second hand: it pauses. No buttons." GRIP-9000 mocks the pause.
5. **Fist again**: 3-2-1, back in.
6. Play out the timer or lose the last life → **game over roast** (live from Claude).

**1:30 to 2:00, how it works** (slide or just talk over the game-over screen)
> "Three threads on one laptop. Vision: MediaPipe gives us 21 points on your hand, and our own maths
> turns them into grip, open and the blade angle: finger curl from the 3D landmarks, a stabiliser,
> One Euro smoothing. Nothing is trained. The game runs at 60 frames a second. And the rival decides
> *when* to speak: small moments come from a pre-voiced bank so they're instant; the big moments are
> written live by Claude and voiced by ElevenLabs."

**2:00 to 2:20, numbers** (show `results/numbers_slide.png`)
> "We measured it live: [[NN]] milliseconds from camera to game, [[NN]] percent of grips and opens recognised
> across [[NNN]] trials with all four of us, both hands, and GRIP-9000 reacts in [[N]] milliseconds for
> the quick lines."

**2:20 to 2:30, close**
> "The brief said: the most interesting moments are over before you could type a prompt.
> GRIP-9000 never needs one. Thank you."

## If something fails (Ananth handles, narrator keeps talking)
| Failure | Do this | Say |
|---|---|---|
| Camera won't open / wrong camera | Restart with `--vision mouse` (hold left button) | "Camera's shy; same game with the mouse as the sword." |
| Tracking flaky (lighting) | Move the lamp / step closer; if still bad → mouse | |
| Wifi / Claude / ElevenLabs down | Restart with `--rival real --offline` (pre-voiced bank) | nothing; it still talks |
| Game crashes | Restart: `python main.py --vision real --game real --rival real` (about 10 s) | "Live demo, live bugs." |
| Everything dies | Play the backup video (desktop, also on USB) | "Here's one we recorded earlier." |

## Q&A prep
- **"Is this just an API wrapper?"** No: the LLM only writes the big-moment lines. Hand reading, grip maths, smoothing, the game and the rival's timing/priorities are ours.
- **"Did you train a model?"** No. MediaPipe gives landmarks; grip/open is our own geometry.
- **"How does it decide when to talk?"** Priorities per event, cooldowns, a global gap after each line, quiet right after a resume, and pattern detection over your run.
- **"Latency?"** See the slide; the quick lines are pre-voiced, Claude lines are pre-fetched where possible.
