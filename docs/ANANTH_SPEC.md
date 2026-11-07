# Ananth's part: shared/, integration, testing, GRIP-9000 (the rival)

Agreed spec. Team-wide rules live in `SPEC.md`; this file is the detail for my part.

## Setup
- Python 3.11 in `.venv` via `./setup.sh` (uv). Apple Silicon Mac, run from macOS Terminal (camera permission goes to Terminal).
- `opencv-python-headless==4.12.0.88` (OpenCV 5 and GUI builds bundle SDL, which clashes with pygame). `mediapipe==1.2.2` installed `--no-deps`; Tasks API only (no `mp.solutions.hands`). No torch unless Aaron asks.
- Audio out: laptop speakers or wired (Bluetooth adds ~200 ms).

## Interface additions (announced to the team)
1. `get_latest_frame()` returns `(frame, t)`: RGB, mirrored, read-only; `(None, 0.0)` before the first frame.
2. `game_start` has `duration` and `lives`; `slice` has `fruit`. Build events with `shared.ev_*()`, send with `shared.post_event()`.
3. `rival_lines` dicts may carry `"final": True` (the game over roast).
4. Mixer: `pre_init(MIXER_FREQ, MIXER_SIZE, MIXER_CHANNELS, MIXER_BUFFER)`, then `set_reserved(1)`; channel 0 is the voice. Game multiplies its volumes by `DUCK_LEVEL` while `shared.rival_speaking` is set.
5. Entry points: `game.run(stop_event, mouse_sword)` (main thread), `vision.run(stop_event)`, `agent.run(stop_event, offline)` (daemon threads).
6. Blade: `BLADE_LENGTH` is a fraction of screen height; tip = base + L(cos a, sin a), y down; `-pi/2` points up.
7. Game loop: `clock.tick_busy_loop(60)` (plain `tick` gives ~45 fps on macOS); no `SysFont` (hangs).

## Rival: GRIP-9000
- Smug AI that thinks humans are obsolete; quotes stats like telemetry; British spelling.
- Roasts the play and the player's character as revealed by play. Never appearance, body, gender, race, religion, disability, age or anything sexual. No swearing. Enforced in the prompt plus a banned-word filter.
- Moods: smug (default), gloating (your failures), rattled (your streaks/combos), defensive (your new best).

### Timing engine
| event | prio | per-event cooldown | talk chance |
|---|---|---|---|
| game_over | 100 | - | 100% (final) |
| bomb_hit | 90 | 4 s | 100%, interrupts |
| life_lost (0-1 left) | 85 | - | 100% (merged with bomb) |
| time_warning | 70 | - | 100% |
| streak (5, 10, 15+) | 60 | 8 s | 90% |
| combo (>= 4) | 55 | 6 s | 80% |
| streak_broken (>= 5) | 50 | 6 s | 90% |
| pause | 45 | 10 s | 70% |
| resume | 40 | 10 s | 50% |
| pattern call-out | 35 | 20 s | via Claude |
| miss | 30 | 5 s | 45% |
| game_start / sword_drawn | 20 | - | 100% once |
| slice | 10 | 12 s | 10% |

Global gap 2.5 s after a line ends (bomb and game_over ignore it). Higher priority interrupts; equal or lower is dropped, never queued.

Pause: let the current line finish, drop queued ones, wait 1.5 s (a resume first means it was a flicker, say nothing), then mock by reason; one follow-up after 8 s; gameplay heckles suppressed for 2 s after resume.

### Stats and patterns
Score, slices, misses L/R, bombs, lives, current/best streak, best combo, pauses by reason, paused time, time left, time since last line, last 5 events.
Patterns (checked every 1 s): side bias (>= 3 misses on one side and >= 2x the other), bomb magnet (2 bombs in 15 s), pause addict (>= 3 pauses), slump (no slice for 6 s in play), comeback (streak >= 5 after losing a life), last life.

### Claude (claude-haiku-5-5, thinking off, max_tokens ~80, streamed)
Moments: game over roast (final), new best (`data/best.json`), streak 10 and 15+, pattern call-outs, halfway commentary, rematch memory (`data/session.json`), last life and time warning.
Pre-fetch: every ~4 s during play, write AND voice (PREVOICE = True) stats-aware lines for the likely next bomb_hit, streak_broken, life_lost and miss; stale ones discarded.
Live timeout: **1.8 s** (measured Haiku 1.1 to 1.5 s per line, warm), then a bank line.
Prompt: fixed system prompt (persona, rules, guardrails) plus a per-call stats snapshot and moment; plain-text output, filtered before speaking.

### Voice (ElevenLabs)
**Voice: Edward (`zYcjlYFOd3taleS0gkk3`, ElevenLabs shared library, "Loud, Confident and Cocky"; 730-day notice period once added to My Voices).** Bank lines cached with `eleven_multilingual_v2`; live lines streamed with `eleven_flash_v2_5` (PCM 22,050 Hz, upsampled 2x) on one warm connection. Cache key sha1(text + voice + model), `assets/voice/cache/` (committed). Voice chosen by `tools/audition_voices.py`.
Measured: Flash first audio ~240 ms warm. 17M characters available, so pre-voicing is affordable.

### Fallbacks
Claude slow/error/filtered: bank line. ElevenLabs fails or > 1 s to first audio: subtitle plus robot blip. 3 network failures in 30 s: offline for the rest of the run. `--offline` forces it.

### Subtitles
Pushed to `rival_lines` when audio starts. Duration: clip length + 0.5 s (cached), max(1.5, words / 2.7) + 0.5 s (streamed). Newest line replaces the bubble.

### Latency targets (p95, event to first audio)
Cached and pre-voiced lines < 300 ms; live Claude lines < 2.1 s.

## Tools
`tools/smoke_test.py`, `tools/bug_report.md`, `tools/check_keys.py`, `tools/audition_voices.py`, then `tools/fake_events.py`, `--record`, `logs/latency.csv` + `tools/latency_report.py`, `tools/voice_bank.py`, `tools/el_quota.py`, `tests/test_timing.py`.

## Milestones
1. shared/ and main.py skeleton on staging (PR #1).
2. Voice chosen, ~40 bank lines voiced, rival speaks cached lines from fake events with subtitles, ducking and timing rules; cached p95 < 300 ms.
3. Real parts wired in as they land; bug report after every merge; rival reacts to real play; recorder works.
4. All Claude moments, ~100 lines, fallbacks and offline mode, latency report; end to end on staging.

## Cut order (first to go at the top)
1. el_quota tool  2. pytest  3. halfway commentary  4. rematch memory  5. pre-fetch
6. Claude for last life / time warning  7. ducking  8. Claude pattern call-outs  9. Claude streaming mid-game.
Never cut: shared/, integration, merge testing, timing engine, voiced bank, subtitles, Claude game over roast.

## Possible fixes (backlog, after real playtesting)
- **Edward talks slightly slowly.** Option A: ElevenLabs `voice_settings={"speed": 1.1 to 1.15}` on both models (bank: re-run `tools/voice_bank.py` after adding it, ~5.6k characters; live: pass it in `LiveTTS.synth`). Option B: shorter word budgets (`LINE_WORDS` 18 -> 14). Try A first; check the Flash and bank voices still match.
- **How much he talks:** tune after playing with the real game (`agent/timing.py` RULES, `GLOBAL_GAP`). `tools/fake_events.py` shows the effect instantly.
