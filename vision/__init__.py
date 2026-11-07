"""Vision: webcam -> MediaPipe landmarks -> grip maths -> stabiliser -> blade -> HandState.

main.py contract:  vision.run(stop_event)  (main.py runs it on a daemon thread)
Publishes shared.set_hand_state(HandState) and shared.set_latest_frame(rgb, t)
once per camera frame, until stop_event is set.

Debug window:  python -m vision.debug
"""
# Heavy imports (OpenCV, NumPy, MediaPipe) happen HERE, when main.py imports this
# package on the main thread. Importing them later inside the vision thread while
# the game loop is running starved the import for 6+ seconds (found by the smoke test).
from vision.thread import VisionLoop


def run(stop_event, camera_index=None):
    VisionLoop(stop_event, camera_index=camera_index).run()
