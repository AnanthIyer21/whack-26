"""WHACK 26: one program, three threads.

    python main.py                              # everything fake
    python main.py --vision mouse               # mouse sword (vision thread not started)
    python main.py --vision real --game real    # mix real and fake parts freely
    python main.py --rival real --offline       # rival with no API calls

Entry-point contract for each part (all loops exit when stop_event is set):
    vision.run(stop_event)                  -> daemon thread
    agent.run(stop_event, offline=False)    -> daemon thread
    game.run(stop_event, mouse_sword=False) -> main thread (pygame must own it on macOS);
                                               returns when the player quits
"""

import argparse
import importlib
import importlib.util
import os
import threading
import time

from dotenv import load_dotenv

import shared

JOIN_TIMEOUT = 2.0


def load_part(kind, real_module, fake_module):
    """Import the real part if asked for and it exists on this branch, else the fake."""
    if kind == "real":
        if importlib.util.find_spec(real_module) is not None:
            module = importlib.import_module(real_module)
            print("[main] " + real_module + ": real")
            return module
        print("[main] " + real_module + ": not on staging yet, using fake")
    else:
        print("[main] " + real_module + ": fake")
    return importlib.import_module(fake_module)


def start_thread(name, target, kwargs):
    thread = threading.Thread(target=target, name=name, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


def diag_loop(stop_event):
    """--diag: once a second, print what vision is publishing; save camera snapshots to logs/."""
    root = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(root, "logs", "diag.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    out = open(log_path, "w")
    started = time.monotonic()
    last_frame_t = None
    last_hand_t = None
    frames = 0
    hand_updates = 0
    next_report = started + 1.0
    snapshots = (5.0, 15.0)
    saved = 0
    while not stop_event.is_set():
        frame, frame_t = shared.get_latest_frame()
        if frame is not None and frame_t != last_frame_t:
            last_frame_t = frame_t
            frames += 1
        hand = shared.get_hand_state()
        if hand.t != last_hand_t:
            last_hand_t = hand.t
            hand_updates += 1
        now = time.monotonic()
        if saved < len(snapshots) and now - started >= snapshots[saved] and frame is not None:
            try:
                import cv2
                path = os.path.join(root, "logs", "diag_frame_" + str(saved + 1) + ".jpg")
                cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                line = "[diag] saved camera snapshot " + path
                print(line)
                out.write(line + "\n")
            except Exception as exc:
                print("[diag] snapshot failed: " + repr(exc))
            saved += 1
        if now >= next_report:
            frame_age = "none" if frame is None else str(round((now - frame_t) * 1000)) + " ms"
            hand_age = "never" if hand.t <= 0 else str(round((now - hand.t) * 1000)) + " ms"
            shape = "" if frame is None else " " + str(frame.shape[1]) + "x" + str(frame.shape[0])
            line = ("[diag] t=" + str(round(now - started)) + "s  frames/s=" + str(frames)
                    + " (latest " + frame_age + shape + ")  hand updates/s=" + str(hand_updates)
                    + " (age " + hand_age + ")  hands=" + str(hand.hands_in_frame)
                    + " grip=" + str(hand.sword_active) + " visible=" + str(hand.sword_visible)
                    + " conf=" + str(round(hand.confidence, 2)) + " angle=" + str(round(hand.blade_angle, 2)))
            print(line)
            out.write(line + "\n")
            out.flush()
            frames = 0
            hand_updates = 0
            next_report = now + 1.0
        stop_event.wait(0.01)
    out.close()


def main():
    parser = argparse.ArgumentParser(description="WHACK 26: one-hand sword fruit game with a heckling rival")
    parser.add_argument("--vision", choices=("fake", "mouse", "real"), default="fake")
    parser.add_argument("--game", choices=("fake", "real"), default="fake")
    parser.add_argument("--rival", choices=("fake", "real"), default="fake")
    parser.add_argument("--offline", action="store_true", help="rival uses the bank only, no API calls")
    parser.add_argument("--diag", action="store_true", help="print vision health every second; save camera snapshots to logs/")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    game = load_part(args.game, "game", "fakes.fake_game")
    rival = load_part(args.rival, "agent", "fakes.fake_rival")
    threads = []

    mouse_sword = args.vision == "mouse"
    if mouse_sword:
        print("[main] vision: mouse (hold the left button to grip)")
    else:
        vision = load_part(args.vision, "vision", "fakes.fake_vision")
        threads.append(start_thread("vision", vision.run, {"stop_event": shared.stop_event}))

    threads.append(start_thread("rival", rival.run, {"stop_event": shared.stop_event, "offline": args.offline}))
    if args.diag:
        threads.append(start_thread("diag", diag_loop, {"stop_event": shared.stop_event}))

    try:
        game.run(shared.stop_event, mouse_sword=mouse_sword)
    except KeyboardInterrupt:
        print("\n[main] Ctrl+C")
    finally:
        shared.stop_event.set()
        stopped_at = time.monotonic()
        for thread in threads:
            thread.join(JOIN_TIMEOUT)
            if thread.is_alive():
                print("[main] WARNING: " + thread.name + " did not stop within " + str(JOIN_TIMEOUT) + " s")
        try:
            import pygame
            pygame.quit()
        except Exception:
            pass
        print("[main] stopped in " + str(round((time.monotonic() - stopped_at) * 1000)) + " ms")


if __name__ == "__main__":
    main()
