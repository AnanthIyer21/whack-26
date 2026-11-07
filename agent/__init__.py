"""GRIP-9000, the rival. Owner: Ananth.

main.py calls agent.run(stop_event, offline=False) on a daemon thread.
"""


def run(stop_event, offline=False):
    # Until agent/rival.py lands, behave like the fake rival so --rival real still runs.
    from fakes import fake_rival
    print("[agent] real rival not wired yet: using fake rival")
    fake_rival.run(stop_event, offline=offline)
