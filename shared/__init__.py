"""Shared foundation. Owner: Ananth. Don't change without telling the team.

    import shared
    shared.get_hand_state()          # vision -> game
    shared.post_event(shared.ev_slice("apple"))   # game -> rival
    shared.rival_lines.get_nowait()  # rival -> game
    frame, t = shared.get_latest_frame()
    shared.stop_event.is_set()       # every thread loop checks this
"""

import threading

from shared.constants import *  # noqa: F401,F403
from shared.hand_state import HandState, get_hand_state, set_hand_state, mouse_hand_state  # noqa: F401
from shared.frame import get_latest_frame, set_latest_frame  # noqa: F401
from shared.events import *  # noqa: F401,F403
from shared.rival import rival_lines, rival_speaking, post_rival_line  # noqa: F401
from shared.pacing import FramePacer  # noqa: F401

# Set once by main.py on shutdown; every thread loop exits when it is set.
stop_event = threading.Event()
