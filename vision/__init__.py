"""Vision: webcam -> MediaPipe landmarks -> grip maths -> stabiliser -> blade -> HandState.

Usage (main.py):
    stop = threading.Event()
    thread = vision.start(publish_state, publish_frame, stop)
publish_state(**fields) gets HandState's fields once per frame;
publish_frame(rgb) gets the mirrored read-only RGB frame.
"""


def start(publish_state, publish_frame, stop_event, publish_debug=None, camera_index=None):
    from vision.thread import VisionThread
    t = VisionThread(publish_state, publish_frame, stop_event, publish_debug, camera_index)
    t.start()
    return t
