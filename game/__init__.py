"""The game (Pricysquirrl). Team contract (see main.py):

    game.run(stop_event, mouse_sword=False)  -> runs on the main thread, returns when the
                                                player quits or stop_event is set.

mouse_sword=True: the mouse is the sword (vision isn't running), and the game publishes its
own HandState so everything else still sees one. It also opens the webcam itself just for
the background (game/camera_feed.py), since no vision thread is using it.
"""


def run(stop_event=None, mouse_sword=False, fullscreen=False, camera=True, **inject):
    """camera: in mouse mode (no vision thread), open the webcam just for the background."""
    from .link import resolve
    from .app import App

    links = resolve(stop_event, **inject)
    if mouse_sword and camera and not inject.get("get_latest_frame"):
        from . import camera_feed
        camera_feed.start(links.stop_event)
    App(links, fullscreen=fullscreen, input_mode="mouse" if mouse_sword else "hand").run()
