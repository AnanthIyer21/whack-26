"""Run the game on its own with the mouse sword and Ananth's fake rival:

    python -m game [--fullscreen] [--fake-vision]

(The full program is python main.py --game real --vision mouse, which does the same.)
"""
import argparse
import threading

import shared
from fakes import fake_rival, fake_vision

from . import run

p = argparse.ArgumentParser(description="Run the game standalone (fake rival).")
p.add_argument("--fullscreen", action="store_true")
p.add_argument("--fake-vision", action="store_true", help="use the fake vision thread instead of the mouse")
p.add_argument("--no-camera", action="store_true", help="mouse mode without the webcam background")
a = p.parse_args()
threading.Thread(target=fake_rival.run, kwargs={"stop_event": shared.stop_event, "offline": True},
                 daemon=True).start()
if a.fake_vision:
    threading.Thread(target=fake_vision.run, kwargs={"stop_event": shared.stop_event}, daemon=True).start()
try:
    run(shared.stop_event, mouse_sword=not a.fake_vision, fullscreen=a.fullscreen, camera=not a.no_camera)
finally:
    shared.stop_event.set()
    import time
    import pygame
    time.sleep(0.3)          # let the other threads stop before pygame goes away
    pygame.quit()
