"""The only file that touches teammates' code.

Uses Ananth's shared/ if it exists, otherwise game/fakes.py. Every call here is
non-blocking and any error from other code is caught and logged once, so the
game never freezes or crashes because of vision or the rival.
"""
import queue
import time

try:
    import shared as _src
    SOURCE = "shared"
except ImportError:
    from game import fakes as _src
    SOURCE = "fakes"

events = getattr(_src, "events", None)
rival_lines = getattr(_src, "rival_lines", None)
BLADE_LENGTH = getattr(_src, "BLADE_LENGTH", 0.30)
standalone = False
_warned = set()


def _warn_once(key, err):
    if key not in _warned:
        _warned.add(key)
        print(f"[game.bridge] {key} failed: {err!r} (game keeps running)")


def setup(events=None, rival_lines=None):
    """Queues passed in (from main.py) always take precedence."""
    global standalone
    g = globals()
    if events is not None:
        g["events"] = events
    if rival_lines is not None:
        g["rival_lines"] = rival_lines
    if g["events"] is None:
        g["events"] = queue.Queue()
    if g["rival_lines"] is None:
        g["rival_lines"] = queue.Queue()
    standalone = SOURCE == "fakes" and events is None and rival_lines is None
    print(f"[game.bridge] using {SOURCE}, standalone={standalone}")
    if standalone:
        _src.start_fake_rival(g["events"], g["rival_lines"])


def get_hand_state():
    try:
        return _src.get_hand_state()
    except Exception as e:  # noqa: BLE001 - never let vision crash the game
        _warn_once("get_hand_state", e)
        return None


def set_sword_hand(hand):
    try:
        _src.set_sword_hand(hand)
    except Exception as e:  # noqa: BLE001
        _warn_once("set_sword_hand", e)


def get_latest_frame():
    try:
        return _src.get_latest_frame()
    except Exception as e:  # noqa: BLE001
        _warn_once("get_latest_frame", e)
        return None


def send_event(type_, **fields):
    """Put one event on the queue without ever blocking."""
    ev = {"type": type_, "t": time.monotonic(), **fields}
    try:
        events.put_nowait(ev)
    except Exception as e:  # noqa: BLE001
        _warn_once("send_event", e)
    return ev


def drain_rival_lines():
    """All rival lines waiting right now (possibly none). Never blocks."""
    out = []
    while True:
        try:
            out.append(rival_lines.get_nowait())
        except queue.Empty:
            return out
        except Exception as e:  # noqa: BLE001
            _warn_once("rival_lines", e)
            return out
