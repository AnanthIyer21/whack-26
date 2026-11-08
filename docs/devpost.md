# Devpost draft: GRIP-9000

> Owner: RBadiadka7. Paste each section into Devpost (https://whack-2026.devpost.com). Fill in the `[[...]]`
> numbers from `results/` after the reliability check. Never call the grip detection a "trained model".
>
> **Rules (checked on the WHACK 2026 Devpost, 8 Nov):** deadline 11:00 GMT; must have a **team name**; **all
> four collaborators linked** to the Devpost project; built during the hackathon; must have attempted ONE title
> sponsor problem statement (we pick **incident.io**). Submit "with plenty of images". **No video is required.**
> Judging is a **3 minute slot** presenting to the chosen sponsor in the afternoon (live demo, slides, anything).
> We're also automatically in WHACKiest Hack and Most Creative.

## Team name
The Flairy Fairies

## Project name
GRIP-9000: Fruit Ninja with a real sword grip and a rival who never shuts up

## Tagline (one line)
Make a fist, draw a sword, slash fruit through your webcam, while a smug AI pineapple roasts you live.

## Challenge
incident.io: "Build an agent that reacts to a live feed as it happens, with personality."

## Inspiration
Most AI waits for you to type. We wanted one that watches you in real time and reacts before you could ever write a prompt, and we wanted it to be *annoying*. Nothing is more live than a game where you swing a sword with your hand, and nothing has more personality than a rival who laughs when you hit a bomb.

## What it does
- Hold one hand up and **make a fist: a sword appears in it**. The blade follows the tilt of your fist, so you slash fruit by swinging it like a real sword.
- Fruit flies up; cut it with a fast swing for points, combos and streaks. Hit a bomb and you lose one of 3 lives. A run lasts 60 seconds.
- **Auto-pause:** open your hand, drop it, or bring in a second hand and the game freezes instantly. Close your fist again for a 3-2-1 and you're back.
- **GRIP-9000**, a smug pixel-art pineapple, watches every move and heckles you out loud *in the moment*: it cackles when you hit a bomb, gets rattled when you're on a streak, mocks you for pausing, and spots your habits (always missing on the left? it notices). Its big-moment roasts are written live by Claude and voiced by ElevenLabs; everything else comes from a pre-voiced bank so it's instant.
- Knife-sharp slash sounds, a whoosh on every swing, music that ducks under the rival's voice.

## How we built it
One Python 3.11 program, three threads talking through small shared interfaces:
- **Vision thread:** OpenCV webcam → **MediaPipe** hand landmarks (21 points per hand, pretrained, not ours) → **our own maths**: finger curl from 3D landmark distances and angles decides grip / open / unclear, with a stabiliser so it doesn't flicker; a One Euro filter smooths the blade; the blade runs along your fist so tilting your fist tilts the sword. Publishes an immutable `HandState` every frame. **Nothing is trained.**
- **Game thread:** pygame-ce at a steady 60 fps. Fruit and blade hitboxes, slicing only above a speed threshold, combos, streaks, bombs, lives, the auto-pause state machine, and lag bridging (if tracking drops a frame, the blade's path is still checked so fast swings don't miss).
- **Rival thread:** reads game events (slice, miss, combo, bomb, pause...) and decides *whether* to speak with priorities, cooldowns and a global gap so it never talks over itself. Small moments use a bank of lines pre-voiced with ElevenLabs (instant). Big moments (game over, last life, patterns in how you play) are written live by **Claude** (claude-haiku-5-5) with a strict persona, then voiced with **ElevenLabs Flash**. Some Claude lines are pre-fetched and pre-voiced before they're needed.
- **Art and sound:** all pixel art drawn in code by us (the pineapple's four moods, fruit and halves, sword, explosions); CC0 sound effects layered and processed into a metal-clash-plus-knife-scrape slash.

## Challenges we ran into
- **Grip without training:** telling a fist from an open or half-open hand from landmark geometry alone, for different hands and both left and right, and making it stable enough that the game doesn't pause by accident.
- **Real-time on one laptop:** three threads in Python. `clock.tick(60)` only reached ~39 fps on macOS and busy-waiting starved the vision and rival threads; we wrote our own frame pacer.
- **Library traps:** OpenCV 5 and the GUI builds bundle SDL and clash with pygame; MediaPipe 1.2.2 dropped the old hands API; pygame-ce's `find_channel()` ignores reserved channels, which silently swallowed every sound effect until we picked channels ourselves.
- **Talking at the right time:** an agent that comments on *everything* is unbearable. The hard part was timing: priorities, cooldowns, and staying quiet right after you resume.
- **Latency of a voice:** a live Claude + TTS line takes over a second; we hide it with pre-voiced banks and pre-fetching so the reaction lands while the moment is still happening.

## Accomplishments that we're proud of
- [[NN]]% grip/open recognition across [[NNN]] live trials, 4 people, both hands, with no training.
- [[NN]] ms from camera frame to game state; the rival reacts to bank-line moments in about [[N]] ms.
- A rival with an actual personality and comic timing, not a chatbot bolted onto a game.
- It's genuinely fun, and genuinely rude.

## What we learned
- Pretrained landmarks plus a little geometry go a long way; you don't need to train a model to read a hand.
- For a live agent, *when* to speak matters more than *what* to say.
- Measure everything: our latency and reliability numbers changed what we fixed.

## What's next for GRIP-9000
- Free-hand gesture moves (block, special attack) and facial reactions to what the player does.
- Two-player duels, with GRIP-9000 commentating both.
- A memory of your past runs so the roasts get personal.

## Built with
`python` `pygame-ce` `opencv` `mediapipe` `numpy` `claude` `anthropic-api` `elevenlabs` `multithreading`

## Links
- Code: https://github.com/AnanthIyer21/whack-26
- Video (optional, not required by the rules): [[YouTube unlisted link]]

## Team
Aaron (vision), Pricysquirrl (game), RBadiadka7 (art and sound, reliability, demo), Ananth (integration, testing, the rival). **Add all four to the Devpost project.**

## Screenshots to upload (take on the demo laptop, `Cmd+Shift+4`)
1. Mid-slash: sword drawn, fruit halves flying, combo popup.
2. GRIP-9000 laughing after a bomb (explosion + speech bubble).
3. The pause screen (open hand) with the Quit button.
4. Game over screen with the final roast.
5. `results/numbers_slide.png`.
6. The vision debug window (skeleton, curl bars, blade).
