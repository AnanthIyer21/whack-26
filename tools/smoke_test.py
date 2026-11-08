"""Smoke test for every merge into staging. Prints PASS/FAIL per check.

    python tools/smoke_test.py                       # all fakes
    python tools/smoke_test.py --game real --rival real --seconds 15

Runs the game with a hidden window (SDL dummy driver), so no camera or screen
needed unless you pass --vision real.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
import threading
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pygame  # noqa: E402

import shared  # noqa: E402
from main import load_part  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(status + "  " + name + ("  (" + detail + ")" if detail else ""))


def check_hand_state_atomic():
    """A writer publishes states whose x always equals their angle; readers must never see them differ."""
    stop = threading.Event()
    torn = [0]
    reads = [0]

    def writer():
        i = 0
        while not stop.is_set():
            v = (i % 1000) / 1000.0
            shared.set_hand_state(shared.HandState(blade_base=(v, v), blade_angle=v, t=time.monotonic()))
            i += 1

    def reader():
        while not stop.is_set():
            s = shared.get_hand_state()
            if s.blade_base[0] != s.blade_angle:
                torn[0] += 1
            reads[0] += 1

    w = threading.Thread(target=writer)
    r = threading.Thread(target=reader)
    w.start()
    r.start()
    time.sleep(0.5)
    stop.set()
    w.join()
    r.join()
    shared.set_hand_state(shared.HandState())
    check("HandState reads are never torn", torn[0] == 0, str(reads[0]) + " reads, " + str(torn[0]) + " torn")


def check_event_builders():
    built = (
        shared.ev_game_start(60, 3), shared.ev_sword_drawn(), shared.ev_sword_sheathed(),
        shared.ev_slice("apple"), shared.ev_miss("left"), shared.ev_combo(3), shared.ev_streak(5),
        shared.ev_streak_broken(5), shared.ev_bomb_hit(), shared.ev_life_lost(2),
        shared.ev_pause("no_hand"), shared.ev_resume(), shared.ev_time_warning(10),
        shared.ev_game_over(100, 3, 60, "timer"), shared.ev_face("smiling", 0.5),
        shared.ev_whiff(), shared.ev_party_over([{"name": "A", "score": 10}]),
    )
    seen = set()
    for e in built:
        seen.add(e["type"])
    check("every event type has a builder", seen == set(shared.EVENT_TYPES))
    rejected = False
    try:
        shared.ev_miss("middle")
    except ValueError:
        rejected = True
    check("bad event fields are rejected", rejected)


def run_program(args):
    game = load_part(args.game, "game", "fakes.fake_game")
    rival = load_part(args.rival, "agent", "fakes.fake_rival")
    vision = load_part(args.vision, "vision", "fakes.fake_vision")

    # Count frames by wrapping display.flip.
    frames = [0]
    first_flip = [0.0]
    real_flip = pygame.display.flip

    def counting_flip():
        if frames[0] == 0:
            first_flip[0] = time.monotonic()
        frames[0] += 1
        real_flip()

    pygame.display.flip = counting_flip

    # Count rival lines by wrapping post_rival_line's queue.
    lines_before = shared.rival_lines.qsize()
    lines_posted = [0]
    real_put = shared.rival_lines.put_nowait

    def counting_put(item):
        lines_posted[0] += 1
        real_put(item)

    shared.rival_lines.put_nowait = counting_put

    stop = shared.stop_event
    threads = []
    parts = [
        ("vision", vision.run, {"stop_event": stop}),
        ("rival", rival.run, {"stop_event": stop, "offline": not args.online}),
    ]
    if args.face:
        import face
        parts.append(("face", face.run, {"stop_event": stop}))
    for name, target, kwargs in parts:
        t = threading.Thread(target=target, name=name, kwargs=kwargs, daemon=True)
        t.start()
        threads.append(t)

    timer = threading.Timer(args.seconds, stop.set)
    timer.start()
    started = time.monotonic()
    game_error = None
    try:
        game.run(stop, mouse_sword=False)
    except Exception as exc:
        game_error = exc
    ran_for = time.monotonic() - started
    stop.set()
    timer.cancel()

    stop_started = time.monotonic()
    for t in threads:
        t.join(2.0)
    stop_ms = (time.monotonic() - stop_started) * 1000.0
    pygame.display.flip = real_flip
    shared.rival_lines.put_nowait = real_put

    check("game loop ran without crashing", game_error is None, repr(game_error) if game_error else "")
    loop_time = (started + ran_for) - first_flip[0]
    fps = (frames[0] - 1) / loop_time if loop_time > 0 else 0
    check("game holds ~60 fps", fps >= 55, str(round(fps, 1)) + " fps")
    hand = shared.get_hand_state()
    check("vision is publishing HandState", hand.t > 0 and time.monotonic() - hand.t < 1.0)
    frame, frame_t = shared.get_latest_frame()
    check("latest frame available", frame is not None, "" if frame is None else str(frame.shape))
    check("events reach the rival (queue drained)", shared.events.qsize() <= 1, str(shared.events.qsize()) + " left")
    check("rival posts lines", lines_posted[0] + lines_before > 0, str(lines_posted[0]) + " lines")
    if args.face:
        import face
        check("face thread reads frames (~10 Hz)", face.diag.get("fps", 0.0) >= 5,
              str(round(face.diag.get("fps", 0.0), 1)) + " fps, " + str(round(face.diag.get("ms", 0.0), 1))
              + " ms/frame, state " + str(face.diag.get("state")))
        check("face thread publishes FaceState", shared.get_face_state().t > 0)
    alive = []
    for t in threads:
        if t.is_alive():
            alive.append(t.name)
    check("threads stop within 2 s", len(alive) == 0, str(round(stop_ms)) + " ms" + (", stuck: " + ", ".join(alive) if alive else ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision", choices=("fake", "real"), default="fake")
    parser.add_argument("--game", choices=("fake", "real"), default="fake")
    parser.add_argument("--rival", choices=("fake", "real"), default="fake")
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--online", action="store_true", help="let the real rival call Claude and ElevenLabs")
    parser.add_argument("--face", action="store_true", help="also run the face extension thread")
    args = parser.parse_args()

    check_hand_state_atomic()
    check_event_builders()
    run_program(args)
    pygame.quit()

    failed = 0
    for name, ok, detail in results:
        if not ok:
            failed += 1
    print("")
    print("SMOKE TEST: " + ("ALL PASS" if failed == 0 else str(failed) + " FAILED") + " (" + str(len(results)) + " checks)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
