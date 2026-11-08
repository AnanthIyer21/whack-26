"""Wires the game to shared/ (Ananth's package). Anything passed in (tests) wins."""
from dataclasses import dataclass
from typing import Callable

import shared


@dataclass
class Links:
    post_event: Callable            # sends one event dict to the rival, never blocks
    rival_lines: object             # queue.Queue of {"text", "mood", "duration", "final"?}
    rival_speaking: object          # threading.Event: set while the rival's voice plays
    get_hand_state: Callable        # -> shared.HandState
    get_latest_frame: Callable      # -> (RGB array or None, t)
    set_hand_state: Callable        # mouse mode publishes its own HandState
    stop_event: object              # threading.Event: the game returns when it is set
    blade_length: float
    default_seconds: int
    lives: int


def resolve(stop_event=None, post_event=None, rival_lines=None, get_hand_state=None,
            get_latest_frame=None) -> Links:
    return Links(
        post_event=post_event or shared.post_event,
        rival_lines=rival_lines if rival_lines is not None else shared.rival_lines,
        rival_speaking=shared.rival_speaking,
        get_hand_state=get_hand_state or shared.get_hand_state,
        get_latest_frame=get_latest_frame or shared.get_latest_frame,
        set_hand_state=shared.set_hand_state,
        stop_event=stop_event if stop_event is not None else shared.stop_event,
        blade_length=float(shared.BLADE_LENGTH),
        default_seconds=int(shared.DEFAULT_RUN_SECONDS),
        lives=int(shared.LIVES),
    )
