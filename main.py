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


def main():
    parser = argparse.ArgumentParser(description="WHACK 26: one-hand sword fruit game with a heckling rival")
    parser.add_argument("--vision", choices=("fake", "mouse", "real"), default="fake")
    parser.add_argument("--game", choices=("fake", "real"), default="fake")
    parser.add_argument("--rival", choices=("fake", "real"), default="fake")
    parser.add_argument("--offline", action="store_true", help="rival uses the bank only, no API calls")
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
