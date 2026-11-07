"""`python -m game` runs the game on its own (standalone mode, fakes if shared/ is missing)."""
import argparse

import game

parser = argparse.ArgumentParser(description="WHACK 26 Fruit Ninja")
parser.add_argument("--input", choices=["mouse", "hand"], default="mouse")
parser.add_argument("--fullscreen", action="store_true")
parser.add_argument("--debug", action="store_true")
args = parser.parse_args()

game.run(input_mode=args.input, fullscreen=args.fullscreen, debug=args.debug)
