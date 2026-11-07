"""The vision thread: owns the camera, runs the pipeline, publishes every frame."""
import threading
import time
import traceback

from vision import config
from vision.capture import Camera, CameraError
from vision.pipeline import VisionPipeline


class VisionThread(threading.Thread):
    def __init__(self, publish_state, publish_frame, stop_event, publish_debug=None, camera_index=None):
        super().__init__(name="vision", daemon=True)
        self.publish_state = publish_state
        self.publish_frame = publish_frame
        self.publish_debug = publish_debug
        self.stop_event = stop_event
        self.camera_index = config.CAMERA_INDEX if camera_index is None else camera_index
        self.pipeline = None      # exposed so the debug window can tune it live
        self.error = None         # last fatal error message, for the debug window

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
                    rgb = Camera.to_rgb_mirrored(bgr)
                    c1 = time.perf_counter()
                    fields, debug = self.pipeline.process(rgb, t)
                    p_end = time.perf_counter()
                    rgb.flags.writeable = False   # readers must not modify it
                    self.publish_frame(rgb)
                    self.publish_state(**fields)
                    done = time.perf_counter()
                    if self.publish_debug is not None:
                        ms = debug["ms"]
                        ms["frame_wait"] = (w1 - w0) * 1e3
                        ms["convert"] = (c1 - w1) * 1e3
                        ms["publish"] = (done - p_end) * 1e3
                        ms["total"] = (done - w1) * 1e3   # frame arrived -> HandState published
                        debug["frame"] = rgb
                        debug["fields"] = fields
                        debug["t"] = t
                        self.publish_debug(debug)
                except Exception:
                    traceback.print_exc()     # one bad frame must never kill vision
        finally:
            try:
                self.publish_state(sword_visible=False, sword_active=False, blade_base=(0.5, 0.5),
                                   blade_angle=-1.5707963267948966, hands_in_frame=0,
                                   gesture="none", confidence=0.0, t=time.monotonic())
            except Exception:
                pass
            if cam is not None:
                cam.close()
            if self.pipeline is not None:
                self.pipeline.close()

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
