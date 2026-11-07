# Game spec (Pricysquirrl)

Source of truth for the team interfaces: `SPEC.md` on `main` (d5c7fc8). This file only covers the game.
Laptop: Intel Mac, Python 3.11, pygame-ce (new to pygame, so the code stays plain and commented).

## 1. Run it

```
python -m game                      # mouse, windowed 1280x720
python -m game --input hand         # read get_hand_state() (fake until vision lands)
python -m game --fullscreen --debug # F toggles fullscreen at any time, D toggles debug overlay
```

`--input mouse|hand` picks the input source at launch (default `mouse`). Tab still toggles during play for testing.

## 2. Connecting to teammates (never blocks)

`game/bridge.py` is the only file that touches other people's code:

- `import shared` if it exists (Ananth's), otherwise `game/fakes.py`, which follows SPEC.md exactly.
- Reads: `get_hand_state()` (a non-blocking copy), `rival_lines.get_nowait()` drained every frame, `get_latest_frame()` (preview, extra).
- Writes: `events.put_nowait(dict)`, `set_sword_hand("left"|"right")`.
- Any exception from teammates' code is caught and logged once. The game keeps running.
- The fake rival (only when `shared` is missing) prints each event and answers some of them with canned lines, so the bubble and avatar can be tested.
- **Queues passed to `game.run(events, rival_lines)` always win** over imported or fake ones. The fake rival only starts in standalone mode (`python -m game` with no `shared`).
- The only vision-related code here is `fakes.py`, a stand-in for testing. Real vision is Aaron's.

We don't write `shared/` or `main.py`. Ananth owns them (SPEC.md). Once they're on `staging`, we merge staging and check that `bridge.py` picks them up. The game also exposes `game.run(events, rival_lines)` for Ananth's `main.py`.

## 3. Screen and loop

- Everything is drawn onto a fixed 1280x720 canvas, then scaled to the window (letterboxed in fullscreen). F toggles fullscreen.
- 60 fps with `clock.tick(60)`. **Simulation time**: fruit, particles and timers use `dt` (seconds, capped at 1/20 so a hitch never teleports fruit).
- **Tracking time is separate**: tip speed uses the real time between two *valid input samples* (`HandState.t` for hand, `time.monotonic()` for mouse), never the capped `dt`. Freshness checks use `time.monotonic()`.
- Scenes: **Title → Countdown → Play ⇄ Pause → GameOver → (Title or Countdown)**.

## 4. Title screen

- Two katana icons, "LEFT" and "RIGHT". Pick with the L or R key or a mouse click. The choice is highlighted, and `set_sword_hand()` is called at once.
- Space, Enter, or a fist (`sword_active` held for 0.5 s, hand input only) starts the countdown. Esc quits.
- The last choice is remembered for Play Again.

## 5. Countdown

A big 3-2-1-SLICE! (0.8 s per step, with a beep slot). Used at game start and after resume. `game_start` is sent when "SLICE!" shows (new rounds only).

## 6. Input (`game/input.py`)

```
class InputSource:
    def update(dt) -> SwordInput   # SwordInput(active, visible, base_px, angle, t)
```

- **MouseInput**: left button held = sword active. Base = mouse position. Angle = direction of motion (smoothed) while moving faster than 150 px/s; while still, Q and E rotate it at 4 rad/s.
- **HandInput**: a new sample only exists when `HandState.t` changes. Vision may run at about 30 fps while the game runs at 60, so on frames with no new sample, cut checks are skipped (the blade is still drawn). Maps `blade_base` (0 to 1) to canvas pixels. `active = sword_active and sword_visible and fresh`. *Fresh* means `now - t < 0.25 s`.
  - The hand is lost (`not sword_visible` or stale): sheathe immediately, then **auto-pause after 1.0 s** of continuous loss (play scene only).
  - `pause_pose` turning true (rising edge) → pause. `pause_pose` must go false again before it can pause again.

## 7. Sword (`game/sword.py`)

- Katana: thin, slightly curved silver blade with a dark edge line, a gold guard, and a wrapped hilt drawn at the base. Tip = base + `BLADE_LENGTH` × 720 px along the angle.
- `BLADE_LENGTH` comes from `shared` (default 0.30 in the fake). In debug, [ and ] adjust it live and show the value, so we can tune it.
- States: `sheathed → drawing (0.12 s, length grows 0→1, glint, can't cut) → drawn → fading (0.15 s alpha out, can't cut)`.
- `sword_drawn` and `sword_sheathed` events fire on the state change, with debounce: a sheathe is sent only if the sword stays sheathed 0.2 s, so tracking flicker doesn't flood the rival.
- **Trail** (top juice priority): ribbon of the last ~0.12 s of tip and mid-blade positions, white-cyan with additive glow, tapering and fading. Only shows when the tip is moving fast.

## 8. Slicing (`game/slicing.py`, unit-tested)

- **Blade history reset**: the previous blade segment and the trail are cleared on draw, tracking loss or recovery, resume, input-source switch, scene change, and whenever the gap between samples is more than 0.1 s. Cut checks need two consecutive valid samples, so a reset can never produce a screen-wide slash.

- Each frame the old blade segment (base0→tip0) and the new one (base1→tip1) form a quad.
- Tip speed = |tip1 − tip0| / dt. Cutting needs `speed ≥ CUT_SPEED` (start at **900 px/s**; in debug, - and = adjust it, and the live speed is shown).
- A fruit is cut if its circle touches the swept area. If the blade moved more than ~40 px or rotated more than 0.3 rad, the move is split into sub-steps, so fast swings never skip a fruit.
- Cut direction = the direction the tip moved. The halves split perpendicular to it.
- **Bombs follow the same rule.** A bomb only goes off when hit above `CUT_SPEED`, so a still sword resting on a bomb is safe.

## 9. Fruit and difficulty (`game/fruit.py`)

| Type | Radius | Juice | Points |
|---|---|---|---|
| watermelon | 52 | red | 1 |
| orange | 36 | orange | 1 |
| apple | 34 | light green | 1 |
| banana | 40 (ellipse) | yellow | 1 |
| strawberry | 26 | red | 1 |
| golden (rare) | 32 | gold sparkles | 10 |
| bomb | 34 | — | — |

- Thrown from below the bottom edge with x in 10–90%, an upward speed chosen so the peak lands at 40–85% of the screen height, a sideways drift toward the centre, gravity ~1400 px/s², and spin of ±4 rad/s.
- Difficulty `d = min(1, elapsed/90 s)`:
  - Throw gap: 1.4 s → 0.7 s.
  - Volley size: 1 → 3–5.
  - Bomb chance per item: 5% → 18%.
  - Golden: 2% per volley after 20 s.
- Sliced fruit becomes two halves (the sprite or shape cut in two) that spin apart under gravity, with juice particles and a juice splat on the background that fades over 3 s.

## 10. Rules (`game/rules.py`, unit-tested, no pygame)

- **Score**: +points per fruit (doubled later by peace).
- **Combo**: a run of cuts, each less than 0.25 s after the previous one. The run ends when 0.25 s passes with no new cut, or the sword is sheathed, even if the blade keeps moving. Continued motion can then start a new run. A run of n ≥ 3 gives +n bonus, a "COMBO ×n" pop-up, and a `combo(n)` event. Any pending combo is settled before the final score is calculated (bomb, lives, quit).
- **Streak**: fruit cut in a row without a drop. A `streak(n)` event at n = 5, 10, 15, and so on. A drop resets it, and `streak_broken(n)` is sent if n ≥ 5.
- **Lives**: 5. Any uncut fruit leaving the bottom (golden included) → `miss(fruit, side)` (side from x < 0.5 of the screen width), then `life_lost(lives_left)`. Bombs leaving the screen are free. 0 lives → game over (reason `lives`).
- **Bomb hit** → gameplay locks **immediately**: no slicing, spawning or life loss from then on. `bomb_hit` is sent once, right away. Time freezes 0.4 s with a white flash, then explosion and screen shake for 1.2 s, then `game_over(reason="bomb")` is sent once. The same "game over once" guard applies to the lives and quit endings.
- Q on the pause screen → `game_over(reason="quit")`, back to title.

## 11. Pause

- Triggers: `pause_pose` rising edge, P key, or the hand lost for 1 s → `pause` event.
- The world freezes, dims and blurs (darken plus a downscaled copy). Shows "PAUSED", "Make a fist to resume" and a small icon of the chosen sword hand. The rival bubble keeps working.
- Resume: fist held 0.5 s (`sword_active`), or P or Space → `resume` event → 3-2-1 countdown → play.
- Q → quit to title.

## 12. Rival on screen (`game/rival_view.py`)

- Top-right avatar, code-drawn (head, brows, eyes, mouth):
  - smug: half-lidded eyes and a smirk.
  - rattled: wide eyes, sweat drop and a wobble.
  - defensive: frown and narrowed eyes.
  - gloating: big grin and a bounce.
- Default mood is smug. The mood eases back to smug after the line ends.
- Speech bubble to the left of the avatar: wrapped text with a typewriter effect (~40 chars/s), held for `duration`, then a 0.3 s fade. A new line replaces the current one.
- The art loads from `assets/rival_<mood>.png` if present (RB's art drops in).

## 13. Game over

- Shows score, best combo, time survived, a "NEW BEST" flag (session best), and the reason ("BOOM" or "Out of lives").
- **Final roast**: when the game ends, the game throws away any queued rival lines, sends `game_over`, and shows "rival is thinking…" dots. Only a line with `"kind": "final_roast"` becomes the roast (if it has a `round_id`, it must match). After 6 s, a canned roast picked using the game stats is shown instead. Untagged lines are never used, because a late mid-game taunt can't be told apart from the roast (this was seen in testing).
- Starting a new round throws away any queued lines, so an old roast never shows up in the next game.
- **Play Again** (Space, Enter, click or fist) works at any moment. T goes back to Title.

## 14. Events sent (all `put_nowait`, all include `"t": time.monotonic()` and `"round_id": int`)

`game_start` · `sword_drawn` · `sword_sheathed` · `slice{fruit}` · `miss{fruit, side}` · `combo{n}` · `streak{n}` · `streak_broken{n}` · `life_lost{lives_left}` · `pause{reason}` · `resume` · `bomb_hit` · `game_over{score, best_combo, duration, reason, want_final_roast}`.
Extension: `gesture{name}`, `special_move{name, fruits_hit}`.

## 15. Proposed interface additions (all optional; the game works without any of them)

1. `"round_id": int` on every event. This is harmless to the rival; nothing depends on it.
2. `game_over` gets `"want_final_roast": true`. `reason` is one of `"bomb" | "lives" | "quit"` (SPEC.md already has `reason`).
3. **For Ananth (one field):** the reply to `game_over` has `"kind": "final_roast"` (it may also copy `round_id`). Without it, the game shows its canned roast after 6 s.
4. `pause` gets `"reason": "pose" | "key" | "hand_lost"`.
5. Ask Aaron: **resume = fist held 0.5 s while paused**. The game handles the timing; vision just keeps publishing `sword_active`. `pause_pose` should drop back to false once the pose is released.
6. `BLADE_LENGTH` in `shared` as a fraction of screen height (0.30 to start).
7. **For Aaron:** `blade_angle` uses screen convention: `atan2(dy, dx)` with y pointing down, so 0 = pointing right, -pi/2 = pointing straight up, and positive = clockwise on screen (after the selfie mirror).

## 16. Sound and art slots (`game/assets.py`)

All optional; a missing file means silence or a code-drawn shape. List for RB (PNG with transparency, WAV or OGG):

- Images: `assets/fruit_<type>.png` (~128 px square, fruit centred), `assets/bomb.png`, `assets/rival_<mood>.png` (256 px), `assets/background.png` (1280×720).
- Sounds: `assets/sfx/swoosh`, `slice`, `draw`, `sheathe`, `fuse`, `boom`, `combo`, `beep`, `go`, `life_lost`, `game_over`.

## 17. Debug overlay (D)

FPS, input source, sword state, tip speed versus `CUT_SPEED`, `BLADE_LENGTH`, HandState age, the swept quad drawn in outline, and the last 5 events.

## 18. Files

```
game/__init__.py      run(events=None, rival_lines=None)
game/__main__.py      CLI flags
game/config.py        all tunables in one place
game/bridge.py        shared/ or fakes
game/fakes.py         fake HandState, queues, set_sword_hand, fake rival
game/app.py           window, canvas, scene switching
game/scenes.py        Title, Countdown, Play, Pause, GameOver
game/input.py         InputSource, MouseInput, HandInput
game/sword.py         katana state, drawing, trail
game/slicing.py       swept-quad geometry (pure)
game/fruit.py         Fruit, Half, Spawner
game/rules.py         score, swing/combo, streak, lives (pure)
game/effects.py       particles, splats, pop-ups, shake, flash
game/rival_view.py    avatar and bubble
game/assets.py        optional image and sound loader
tests/test_slicing.py tests/test_rules.py
requirements-game.txt pygame-ce, pytest
```

## 19. Cut order if we fall behind

Extension 1 → webcam preview → leaderboard → sound polish. Protected: the core loop, sword, slicing, bombs, pause, and the rival avatar and bubble.

## 20. Done criteria

The team checkpoint times in SPEC.md have slipped (it was 16:54 when this was written), so the dates below are our targets.

- **A1, playable core (ASAP, ~17:45)**: `python -m game` with the mouse: title (hand choice), countdown, fruit as plain circles, a simple blade line, swept slice with speed gate, score, combos, streaks, 5 lives, bombs ending the game, game over with Play Again. Every event appears in the fake rival's console with the right fields. Tests pass.
- **A2, visual polish (~18:15)**: katana drawing, draw and fade animation, glowing trail, halves, juice particles, splats, pop-ups, bomb freeze, flash and shake.
- **B, 18:30**: pause screen with all three triggers and fist resume. HandInput against the fake (scripted fist and swing), including the lost-hand auto-pause. Rival avatar and bubble driven by fake lines. Final-roast flow with round_id. Debug overlay.
- **C, 22:00**: merged with Ananth's `shared/` and Aaron's vision on `staging`. Playable with the real sword. `CUT_SPEED` and `BLADE_LENGTH` tuned on the demo laptop. RB's assets drop in.
- **Overnight**: extension 1 effects (keys 1–6, spec them then), juice polish, webcam preview, leaderboard.
