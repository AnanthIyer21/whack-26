"""The game (Pricysquirrl). main.py calls game.run() on the main thread.

Anything main.py passes in is used as given; anything missing comes from shared/,
and only if shared/ is missing too do we fall back to our own fakes (plus a fake rival).
"""


def run(events=None, rival_lines=None, get_hand_state=None, get_latest_frame=None,
        fullscreen=False, input="mouse"):
    from .link import resolve
    from .app import App

    links = resolve(events, rival_lines, get_hand_state, get_latest_frame)
    App(links, fullscreen=fullscreen, input_mode=input).run()
