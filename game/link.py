"""Wires the game to the rest of the program.

Priority for each piece: what main.py passed in -> shared/ -> our own fakes.
A fake rival only starts when we are using our own fake events queue.
"""
from dataclasses import dataclass
from typing import Callable, Optional
import queue

from . import fakes

try:
    import shared as _shared  # Ananth's package, once it's on staging
except ImportError:
    _shared = None


@dataclass
class Links:
    events: queue.Queue
    rival_lines: queue.Queue
    get_hand_state: Callable
    get_latest_frame: Callable
    blade_length: float
    default_seconds: int
    using_fakes: bool


def _from_shared(name: str):
    return getattr(_shared, name, None) if _shared is not None else None


def resolve(events=None, rival_lines=None, get_hand_state=None, get_latest_frame=None,
            start_rival_if_fake=True) -> Links:
    fake_events = False
    if events is None:
        events = _from_shared("events")
    if events is None:
        events, fake_events = fakes.events, True
    if rival_lines is None:
        rival_lines = _from_shared("rival_lines") or fakes.rival_lines
    get_hand_state = get_hand_state or _from_shared("get_hand_state") or fakes.get_hand_state
    get_latest_frame = get_latest_frame or _from_shared("get_latest_frame") or fakes.get_latest_frame
    blade_length = _from_shared("BLADE_LENGTH") or fakes.BLADE_LENGTH
    default_seconds = _from_shared("DEFAULT_GAME_SECONDS") or fakes.DEFAULT_GAME_SECONDS

    if fake_events and start_rival_if_fake:
        fakes.start_fake_rival(events, rival_lines)

    return Links(events, rival_lines, get_hand_state, get_latest_frame,
                 float(blade_length), int(default_seconds), using_fakes=fake_events)
