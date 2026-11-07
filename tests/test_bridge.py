import queue

from game import bridge


def test_passed_queues_win_and_events_have_type_and_t():
    ev_q, lines_q = queue.Queue(), queue.Queue()
    bridge.setup(events=ev_q, rival_lines=lines_q)
    assert bridge.standalone is False
    bridge.send_event("slice", fruit="apple")
    ev = ev_q.get_nowait()
    assert ev["type"] == "slice" and ev["fruit"] == "apple" and isinstance(ev["t"], float)
    lines_q.put({"text": "hi", "mood": "smug", "duration": 2})
    assert bridge.drain_rival_lines() == [{"text": "hi", "mood": "smug", "duration": 2}]
    assert bridge.drain_rival_lines() == []
