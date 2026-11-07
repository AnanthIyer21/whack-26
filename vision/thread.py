"""The vision loop: owns the camera, runs the pipeline, publishes every frame to shared/."""
import threading
import time
import traceback

import shared
from vision import config
from vision.capture import Camera, CameraError
from vision.pipeline import VisionPipeline


class VisionLoop:
    """Runs until stop_event is set. Publishes HandState and the frame to shared/.

    on_debug (optional) gets a per-frame debug packet; only the debug window and
    the latency tool use it.
    """

    def __init__(self, stop_event, on_debug=None, camera_index=None):
        self.stop_event = stop_event
        self.on_debug = on_debug
        self.camera_index = config.CAMERA_INDEX if camera_index is None else camera_index
        self.pipeline = None      # exposed so the debug window can tune it live
        self.error = None         # last camera error message, for the debug window

    def run(self):
        cam = None
        try:
            cam = self._open_camera()
            if cam is None:
                return
            self.pipeline = VisionPipeline(cam.width, cam.height)
            failures = 0
            while not self.stop_event.is_set():
                w0 = time.perf_counter()
                bgr = cam.read_bgr()
                t = time.monotonic()
                w1 = time.perf_counter()
                if bgr is None:
                    failures += 1
                    if failures >= 30:            # ~1 s of nothing: reopen the camera
                        cam.close()
                        cam = self._open_camera()
                        if cam is None:
                            return
                        failures = 0
                    continue
                failures = 0
                try:
                    self._process(bgr, t, w0, w1)
                except Exception:
                    traceback.print_exc()         # one bad frame must never kill vision
        finally:
            try:
                shared.set_hand_state(shared.HandState(t=time.monotonic()))   # no hand
            except Exception:
                pass
            if cam is not None:
                cam.close()
            if self.pipeline is not None:
                self.pipeline.close()

    def _process(self, bgr, t, w0, w1):
        rgb = Camera.to_rgb_mirrored(bgr)
        c1 = time.perf_counter()
        fields, debug = self.pipeline.process(rgb, t)
        p_end = time.perf_counter()
        shared.set_latest_frame(rgb, t)               # made read-only by shared/
        shared.set_hand_state(shared.HandState(**fields))
        done = time.perf_counter()
        if self.on_debug is not None:
            ms = debug["ms"]
            ms["frame_wait"] = (w1 - w0) * 1e3
            ms["convert"] = (c1 - w1) * 1e3
            ms["publish"] = (done - p_end) * 1e3
            ms["total"] = (done - w1) * 1e3           # frame arrived -> HandState published
            debug["frame"] = rgb
            debug["fields"] = fields
            debug["t"] = t
            self.on_debug(debug)

    def _open_camera(self):
        while not self.stop_event.is_set():
            try:
                cam = Camera(index=self.camera_index).open()
                self.error = None
                print("[vision] camera:", cam.info())
                return cam
            except CameraError as e:
                self.error = str(e)
                print("[vision]", e, "- retrying in 1 s")
                self.stop_event.wait(1.0)
        return None


def start_thread(stop_event, on_debug=None, camera_index=None):
    """Run VisionLoop on a daemon thread (debug window / tools). Returns (thread, loop)."""
    loop = VisionLoop(stop_event, on_debug, camera_index)
    t = threading.Thread(target=loop.run, name="vision", daemon=True)
    t.start()
    return t, loop
