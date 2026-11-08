# Face reactions: GRIP-9000 reads your expressions live (extension)

Owner: Ananth. Agreed 8 Nov 2026, ~02:30. Built overnight on `ananth`; merged after the morning play test.
Pitch wording: "GRIP-9000 reads your expressions live." Never "facial recognition". Expressions only, no identity, nothing stored.

## Product
- GRIP-9000 heckles what your face is DOING: **smiling, laughing, shock, frowning, looking away** (5). Never appearance.
- Seasoning, not the main dish: ~2 to 4 face lines per 60 s run, only during actual play, never interrupting.
- No new on-screen UI (voice + the existing speech bubble). Off unless `--face`.

## Face thread (`face/`)
- Reads vision's frames via `shared.get_latest_frame()` (never opens the camera). MediaPipe Face Landmarker
  (Tasks API, VIDEO mode, blendshapes + facial transformation matrix) at 10 Hz on a 640x360 downscale.
  Works with real vision and with `--vision mouse` (the game's webcam feed publishes frames too).
- Player only: up to 3 faces detected, the largest is read; if the two largest are within 25% in size, no face is read.
- Fist over the face: frames where HandState.blade_base is inside the face box (+15% margin) are skipped.
  A lost face never counts as "looking away".
- Rolling per-player baseline: 20th percentile of each signal over the last 20 s; reset after the face is lost > 3 s.
  5 s warm-up: no face events until the baseline has 5 s of data.
- Looking away is measured relative to the player's own usual head position (yaw > 25 deg or pitch > 20 deg down).
- Smoothing (EMA), hysteresis (re-arm only after dropping below a release level), hold times.
  Priority when several hold: laughing > shock > smiling > frowning > looking away.
- `face/config.py`: all thresholds and `ENABLED_EXPRESSIONS` (switch any misfiring expression off with one edit).

| Expression | Fires when (smoothed blendshapes) | Hold |
|---|---|---|
| laughing | smile >= 0.40 (and >= baseline + 0.15) and jawOpen >= 0.30 (and >= baseline + 0.20) | 0.5 s |
| smiling | smile >= 0.45 and >= baseline + 0.25 | 0.6 s |
| shock | jawOpen >= 0.45 and >= baseline + 0.25, smile < 0.30 | 0.4 s |
| frowning | (browDown >= 0.40 and >= baseline + 0.20) or mouthFrown >= 0.35; smile < 0.20 | 0.7 s |
| looking away | yaw > 25 deg or pitch > 20 deg down, relative to baseline | 0.8 s |

## Shared additions (additive only)
- `shared/face.py`: frozen `FaceState` (face_visible, expression, scores, yaw, pitch, faces_in_view, calibrated, t);
  `get_face_state()` / `set_face_state()` (lock-guarded swap, like HandState).
- `shared/events.py`: event type `face`, `ev_face(expression, strength)`, `EXPRESSIONS`. Posted to `shared.events`
  only when an expression fires.

## GRIP-9000 (`agent/`)
- Plain face lines: priority 33, per-expression cooldown 25 s, any-face cooldown 10 s, 70% chance, bank lines.
  Ignored unless the run is in play (not title, countdown, paused or over).
- Combos -> live Claude, priority 45, and they may WAIT up to 4 s for the current line to finish, then speak
  immediately (the only lines that ever wait):
  smiling/laughing within 4 s of a bomb or on the last life; shock within 3 s of a bomb;
  frowning after >= 3 misses in 15 s; looking away during a streak >= 3.
- Moods: smiling/laughing gloating when losing, rattled when winning (3 lives and streak >= 5); shock, frowning gloating; looking away smug.
- Bank: 36 lines (5 expressions x 6, plus rattled smiling/laughing x 3 each), voiced by Edward.
- Claude snapshots gain `player_expression` and `expressions_this_run` (game over roast can use them).
  Prompt guardrail: comment only on the expression, never the face, looks or features. Banned-word filter still applies.

## Tools and tests
- `tools/face_debug.py`: live scores and decisions in the terminal (text only).
- `main.py --diag`: adds a face line each second (face thread ms per frame, faces, expression) next to hand fps.
- `tools/smoke_test.py`: knows `ev_face`; `--face` mode checks the face thread starts, publishes and stops cleanly.
- `tests/test_face.py`: calibration, warm-up, hysteresis, largest face, fist overlap, relative head pose, face timing rules
  (synthetic); plus real-photo tests on Google's MediaPipe sample portraits (downloaded on demand, never committed).

## Done
- Overnight: all tests pass; smoke test passes with and without `--face`; 60 fps; hand fps unchanged; 36 lines voiced;
  replays show <= ~4 face lines per run, all in quiet gaps; PR into staging (not merged); docs/OVERNIGHT_REPORT.md.
- Morning play test: each expression fires when held; 60 s neutral face -> zero face lines; fist over the mouth 5 s ->
  nothing; `--diag` shows no sword lag with a real face. Then tune and merge.
