"""Run the game on its own:  python -m game  [--fullscreen] [--hand]"""
import argparse

from . import run

p = argparse.ArgumentParser(description="Run the game standalone (fakes for vision and rival).")
p.add_argument("--fullscreen", action="store_true")
p.add_argument("--hand", action="store_true", help="start with hand input instead of the mouse")
a = p.parse_args()
run(fullscreen=a.fullscreen, input="hand" if a.hand else "mouse")
