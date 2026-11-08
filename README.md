# whack-26

One-hand webcam sword fruit game with a heckling AI rival (GRIP-9000). See `SPEC.md`.

## Setup (Python 3.11, macOS)

macOS / Linux:
```sh
./setup.sh                 # creates .venv and installs pinned deps (uses uv if you have it)
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
.venv\Scripts\Activate.ps1
```

No API keys needed: without a `.env`, GRIP-9000 runs offline and speaks the pre-voiced bank (committed in `assets/voice/cache/`). Only the demo laptop has `.env` (Claude + ElevenLabs).

Camera access: macOS: System Settings > Privacy & Security > Camera > enable your terminal app, then quit it fully (Cmd+Q) and reopen. Windows: Settings > Privacy & security > Camera > allow desktop apps. Close other apps using the webcam. If the wrong camera opens (e.g. iPhone Continuity Camera), set `CAMERA_INDEX = 1` in `vision/config.py`.

## Run

```sh
python main.py                                  # everything fake
python main.py --vision mouse                   # mouse sword: hold the left button to grip
python main.py --vision real --game real --rival real
python main.py --rival real --offline           # rival with no API calls
python main.py --vision real --game real --rival real --diag   # prints vision health each second
python tools/smoke_test.py                      # automated checks (run after every merge)
```

Each part exposes `run(stop_event, ...)`; see the top of `main.py`. Shared interfaces live in `shared/`.

## Gotchas (already handled in requirements; keep them in mind)

- OpenCV must be `opencv-python-headless` 4.12. OpenCV 5 and the GUI builds bundle SDL, which clashes with pygame. So no `cv2.imshow`: draw debug views in pygame.
- `mediapipe` 1.2.2 has no `mp.solutions.hands`: use the Tasks API (`HandLandmarker` with a `hand_landmarker.task` model file).
- `pygame.font.SysFont` hangs for seconds on macOS: load a TTF from `assets/` (or `pygame.font.Font(None, size)`).
- Frame pacing: use `shared.FramePacer(shared.FPS)` and call `pacer.tick()` each frame. `clock.tick(60)` only reaches ~39 fps on macOS, and `clock.tick_busy_loop(60)` holds Python's lock while spinning, starving the vision and rival threads (~60% less CPU for them).

## Results and credits

- Reliability check (grip/open, 4 people, both hands): `results/reliability_table.md`, produced by `tools/reliability_check.py` + `tools/reliability_summary.py`.
- Pitch numbers slide: `results/numbers_slide.png` (`tools/make_numbers_slide.py`).
- Demo docs (Devpost draft, pitch script, video shot list, Sunday runbook): `docs/`.
- Art: all pixel art drawn in code (`tools/gen_art.py`). Sounds and font: CC0 / OFL, full list in [`assets/CREDITS.md`](assets/CREDITS.md).
