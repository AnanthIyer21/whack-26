# whack-26

One-hand webcam sword fruit game with a heckling AI rival (GRIP-9000). See `SPEC.md`.

## Setup (Python 3.11, macOS)

```sh
./setup.sh                 # creates .venv and installs pinned deps (uses uv if you have it)
source .venv/bin/activate
cp .env.example .env       # only the demo laptop needs real keys
```

Grant camera access to the app you run from (System Settings > Privacy & Security > Camera).

## Run

```sh
python main.py                                  # everything fake
python main.py --vision mouse                   # mouse sword: hold the left button to grip
python main.py --vision real --game real --rival real
python main.py --rival real --offline           # rival with no API calls
python tools/smoke_test.py                      # automated checks (run after every merge)
```

Each part exposes `run(stop_event, ...)`; see the top of `main.py`. Shared interfaces live in `shared/`.

## Gotchas (already handled in requirements; keep them in mind)

- OpenCV must be `opencv-python-headless` 4.12. OpenCV 5 and the GUI builds bundle SDL, which clashes with pygame. So no `cv2.imshow`: draw debug views in pygame.
- `mediapipe` 1.2.2 has no `mp.solutions.hands`: use the Tasks API (`HandLandmarker` with a `hand_landmarker.task` model file).
- `pygame.font.SysFont` hangs for seconds on macOS: load a TTF from `assets/` (or `pygame.font.Font(None, size)`).
- `clock.tick(60)` only reaches ~45 fps on macOS: use `clock.tick_busy_loop(60)`.
