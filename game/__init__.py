"""The Fruit Ninja game (Pricysquirrl). Entry point for main.py: game.run(events, rival_lines)."""


def run(events=None, rival_lines=None, input_mode="mouse", fullscreen=False, debug=False):
    """Run the game on the calling (main) thread until the window closes.

    Queues passed here always win over the ones in shared/ or the fakes.
    """
    from game import bridge
    from game.app import App

    bridge.setup(events=events, rival_lines=rival_lines)
    App(input_mode=input_mode, fullscreen=fullscreen, debug=debug).run()
