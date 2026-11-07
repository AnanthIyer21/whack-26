"""Listen to GRIP-9000's voiced bank.

    python tools/play_bank.py              # list the keys and line counts
    python tools/play_bank.py miss         # play every line for one key
    python tools/play_bank.py pause        # every key starting with "pause"
    python tools/play_bank.py all          # the whole bank (~8 minutes)
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "assets", "voice", "cache")


def main():
    with open(os.path.join(CACHE_DIR, "manifest.json")) as f:
        lines = json.load(f)["lines"]
    by_key = {}
    for text in lines:
        key = lines[text]["key"]
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(text)

    if len(sys.argv) < 2:
        for key in sorted(by_key):
            print(str(len(by_key[key])).rjust(3) + "  " + key)
        print("")
        print("Play one: python tools/play_bank.py <key>   (prefix works, e.g. pause)")
        return

    wanted = sys.argv[1]
    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    for key in sorted(by_key):
        if wanted != "all" and not key.startswith(wanted):
            continue
        print("")
        print("=== " + key)
        for text in by_key[key]:
            print("  " + text)
            channel = pygame.mixer.Sound(os.path.join(CACHE_DIR, lines[text]["file"])).play()
            while channel.get_busy():
                time.sleep(0.05)
            time.sleep(0.35)
    pygame.mixer.quit()


if __name__ == "__main__":
    main()
