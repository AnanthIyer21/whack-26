# Overnight report: face reactions (Sun 8 Nov, ~02:35 to ~04:30)

**Status: built to spec, tested with everything except a real face on camera. PR into `staging` is open, NOT merged.**
Spec: `docs/FACE_SPEC.md`. Everything is behind `--face`; without it GRIP-9000 behaves exactly as before
(replay output identical, line for line, to the pre-face code).

## Your morning (about 10 minutes)

```sh
cd ~/Documents/WHACK26/whack-26-restart && source .venv/bin/activate
python tools/face_debug.py            # 1. text-only view of what the face thread sees (no game)
```
Watch the levels (>= 0 means "on") and the `>>> FIRED` lines while you:
1. Sit **neutral for 15 s** (it calibrates for 5 s): nothing should fire.
2. **Smile**, then a big **laugh**, then **mouth open in shock**, then **frown**, then **turn your head away**: each should fire once.
3. Hold your **fist in front of your mouth** for 5 s: state should say `covered`, nothing fires.

Then the real thing:
```sh
python main.py --vision real --game real --rival real --face --diag
```
4. Play a run. Grin right after hitting a bomb: GRIP-9000 should call it out (live Claude, after his bomb line).
5. In the `[diag]   face:` lines check the face thread is ~10 fps and ~10 ms/frame, and the hand fps is unchanged.

Tell me what fired wrongly (or didn't fire) and I'll tune `face/config.py`. Any expression that keeps misfiring can be
switched off in one edit: `ENABLED_EXPRESSIONS` in `face/config.py`. When happy: `gh pr merge 14 --merge` (PR #14).

## What was built (7 commits on `ananth`)
| Part | Files |
|---|---|
| Shared (additive) | `shared/face.py` (`FaceState`, `get/set_face_state`), `shared/events.py` (`face` event, `ev_face`, `EXPRESSIONS`) |
| Face thread | `face/__init__.py` (`run`), `face/detector.py` (MediaPipe Face Landmarker), `face/expressions.py` (calibration, smoothing, hold, hysteresis, priority), `face/config.py`, `face/models/face_landmarker.task` (3.7 MB) |
| GRIP-9000 | `agent/timing.py` (face rules, cooldowns, combo waiting room), `agent/stats.py`, `agent/rival.py`, `agent/lines.py`, `agent/persona.py` (guardrail + appearance words), `agent/lines.json` + 36 voiced clips |
| Tools | `main.py --face` and face line in `--diag`, `tools/face_debug.py`, `tools/smoke_test.py --face`, `tools/fake_events.py --face` |
| Tests | `tests/test_face.py` (19: rules, photos, thread end to end), 7 new face tests in `tests/test_timing.py` |

## Measured
| Check | Result |
|---|---|
| All tests | **128 passed** (was 102) |
| Smoke test | 10/10 without `--face`, **12/12 with `--face`** |
| Face on real sample photos | broad grin: smile 0.95; slight smile: 0.59; both detected, head pose sensible |
| Face thread end to end (real model, real photos) | calibrated on a slight smile, then fired exactly one `smiling` on a broad grin |
| Face thread cost | ~9.6 fps, **8.5 ms/frame on a real face** |
| Sword lag | hand pipeline 13.4 ms alone vs **13.2 ms with face running on a real face** (no change) |
| Game fps (3 runs each) | 60.0 / 60.0 / 60.0 without; 58.9 / 60.0 / 60.0 with (the 58.9 = face model loading on the title screen) |
| Talk volume (12 replays, expressive player) | 6 to 24 expressions per run -> **1 to 4 face lines spoken** |
| Combos | verified waiting for the bomb / last-life line, then speaking ("laughing right after slicing a bomb") |
| Live Claude combo lines | 0.9 to 1.25 s; expression-only, e.g. "Ah, that scowl says everything: four fruit fallen and no streak to show for it." |
| Without `--face` | replay output identical to the pre-face code |

## Decisions I made for you
1. **Test photos are not committed.** Tests download Google's MediaPipe sample portraits (one is an official
   public-domain portrait of a real public figure) into gitignored `tests/data/` and skip when offline.
2. **Looking away counts head tilt up OR down** (the tilt direction can't be verified without a real test),
   relative to your usual position as agreed.
3. **Laughing got per-player margins** (smile >= your baseline + 0.15, jaw >= baseline + 0.20): a slight
   closed-mouth smile already scores 0.59, so a smiley person *talking* could have read as laughing.
4. Photo data confirmed two spec rules: a big grin pushes "brow down" to 0.80 (so frowning's no-smile guard is
   essential), and a forward-facing person read 18 deg of tilt (so head pose must be relative).
5. **Fist covering the face completely** (face not detected, fist inside the last face box) counts as *covered*,
   not *lost*, so raising your fist doesn't reset calibration.
6. Two similar-size faces count as unreadable (no update), not lost.
7. While a higher-priority expression is on (laughing), lower ones (smiling) are used up rather than firing a
   second heckle a moment later (a test caught this double-fire).
8. A face combo sets `player_expression` to its own expression for Claude (a stale value made Claude say
   "still chuckling" about a frown during testing).
9. A face line cut off by a bomb still counts towards the face cooldowns.
10. The face model loads when the thread starts; it can cost a frame or two on the title screen.

## The 36 face lines (voiced by Edward; edit `agent/lines.json`, then `python tools/voice_bank.py`)
One to double-check: "Frowning burns calories..." is about effort, not bodies, but cut it if it feels off.

**`face.smiling`**: Smiling? Your score disagrees. / I see that smile. I'm logging it as overconfidence. /
Enjoying yourself? That makes one of us. / Grinning won't slice the fruit for you. / Wipe that smile off. The
fruit is still winning. / A smile. Bold, given the evidence.

**`face.smiling.rattled`** (when you're winning): Stop grinning at me. It's unsettling. / Don't smile. You're
making my processors nervous. / Smug, are we? That's my job.

**`face.laughing`**: Laughing at your own score? Fair enough. / Oh, you find this funny? So do I. / Laugh it up.
The leaderboard is laughing too. / Hysterical laughter. Classic sign of defeat. / Glad one of us is amused. /
Laughing? I'll add that to the evidence.

**`face.laughing.rattled`**: Stop laughing. This is a serious competition. / You're laughing? I'm not laughing. I
can't laugh. / Enjoy it while it lasts. It won't last.

**`face.shock`**: Close your mouth. You'll catch fruit flies. / Shocked? I predicted this hours ago. / That face.
Pure, unfiltered panic. / Jaw on the floor. Sword in the air. Priorities. / Surprised? You shouldn't be. /
Speechless. Finally, some peace and quiet.

**`face.frowning`**: Frustrated? Excellent. Keep going. / That frown suggests you've seen your score. / Scowling at
the screen won't help. I've checked. / Ooh, someone's annoyed. / Frowning burns calories. Slicing burns more. /
Angry face detected. Delightful.

**`face.looking_away`**: Eyes on me, human. / Looking away won't make the fruit disappear. / Hello? The game is
over here. / Distracted already? Typical. / Can't bear to watch? Understandable. / Look at the screen. I'm right here.

## Team notes
- **Shared interface additions** (additive; nothing existing changed): `shared.FaceState`, `shared.get_face_state()`,
  `shared.ev_face(expression, strength)`, event type `face` in `shared.events`. The game doesn't need to do anything.
- **RBadiadka7's Devpost** (`docs/devpost.md`, on his branch) lists "facial reactions" under *what's next*. If face is
  in the demo, suggested wording for him:
  > **GRIP-9000 reads your expressions live.** Grin after hitting a bomb and he'll call it out. MediaPipe's face
  > landmarker (pretrained, not ours) gives expression scores; our own code calibrates to each player's resting face,
  > debounces, ignores your fist when it covers your face, and decides when a reaction is worth saying.
  > Expressions only: no identity, nothing stored.
  Never say "facial recognition".
- Overnight, `staging` didn't move; RBadiadka7's demo docs (3 commits) are on his branch, not on `staging` yet.
