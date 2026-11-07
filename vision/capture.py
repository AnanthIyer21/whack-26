"""Webcam capture. Only vision ever opens the camera."""
import cv2
import numpy as np

from vision import config


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, index=config.CAMERA_INDEX, width=config.FRAME_WIDTH,
                 height=config.FRAME_HEIGHT, fps=config.TARGET_FPS):
        self.index, self.req_w, self.req_h, self.req_fps = index, width, height, fps
        self.cap = None

    def open(self):
        backend = cv2.CAP_DSHOW if config.USE_DSHOW else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.index, backend)
        if not cap.isOpened():
            raise CameraError(
                f"Could not open camera {self.index}. Close other apps using the webcam "
                "(Teams, Discord, Camera) and check Settings > Privacy & security > Camera.")
        if config.USE_MJPG:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.req_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.req_h)
        cap.set(cv2.CAP_PROP_FPS, self.req_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # always hand us the newest frame
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            raise CameraError(f"Camera {self.index} opened but returned no frame.")
        self.cap = cap
        self.height, self.width = frame.shape[:2]
        return self

    def read_bgr(self):
        """Blocking read of the raw (unmirrored) BGR frame, or None on failure."""
        ok, frame = self.cap.read()
        return frame if ok else None

    @staticmethod
    def to_rgb_mirrored(frame_bgr):
        """Selfie-mirror and convert to RGB in one pass. Returns a new contiguous array."""
        rgb = cv2.cvtColor(cv2.flip(frame_bgr, 1), cv2.COLOR_BGR2RGB)
        return np.ascontiguousarray(rgb)

    def info(self):
        c = self.cap
        fourcc = int(c.get(cv2.CAP_PROP_FOURCC))
        fourcc_s = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
        return {"backend": c.getBackendName(), "width": self.width, "height": self.height,
                "fps_reported": c.get(cv2.CAP_PROP_FPS), "fourcc": fourcc_s}

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
