"""MediaPipe Face Landmarker wrapper: frame in, the player's face signals out.

Input frames are vision's frames (RGB, selfie-mirrored), so face boxes are in the
same normalised coordinates as HandState.blade_base. Nothing is stored.
"""

import math
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from face import config as C


class Face:
    """One detected face: box (normalised x0, y0, x1, y1), area in pixels, signals and head pose."""

    def __init__(self, box, area, signals, yaw, pitch):
        self.box = box
        self.area = area
        self.signals = signals
        self.yaw = yaw
        self.pitch = pitch


def head_pose(matrix):
    """(yaw, pitch) in degrees from MediaPipe's 4x4 facial transformation matrix."""
    r = np.asarray(matrix, dtype=float)[:3, :3]
    sy = math.sqrt(r[0, 0] * r[0, 0] + r[1, 0] * r[1, 0])
    pitch = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    yaw = math.degrees(math.atan2(-r[2, 0], sy))
    return yaw, pitch


def signals_from_blendshapes(categories):
    scores = {}
    for c in categories:
        scores[c.category_name] = c.score

    def mean(a, b):
        return (scores.get(a, 0.0) + scores.get(b, 0.0)) / 2.0

    return {
        "smile": mean("mouthSmileLeft", "mouthSmileRight"),
        "jaw": scores.get("jawOpen", 0.0),
        "brow": mean("browDownLeft", "browDownRight"),
        "frown": mean("mouthFrownLeft", "mouthFrownRight"),
    }


class FaceDetector:
    def __init__(self, mode="video"):
        running_mode = vision.RunningMode.VIDEO if mode == "video" else vision.RunningMode.IMAGE
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(C.MODEL_PATH)),
            running_mode=running_mode,
            num_faces=C.MAX_FACES,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self.mode = mode
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.last_ts = -1
        self.last_ms = 0.0

    def detect(self, rgb, t=None):
        """All faces in an RGB frame, largest first. t: time.monotonic() of the frame (video mode)."""
        started = time.perf_counter()
        h, w = rgb.shape[0], rgb.shape[1]
        if w > C.DETECT_WIDTH:
            new_h = int(round(h * C.DETECT_WIDTH / float(w)))
            rgb = cv2.resize(rgb, (C.DETECT_WIDTH, new_h), interpolation=cv2.INTER_AREA)
        rgb = np.ascontiguousarray(rgb)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        if self.mode == "video":
            ts = int((t if t is not None else time.monotonic()) * 1000)
            if ts <= self.last_ts:
                ts = self.last_ts + 1          # MediaPipe needs strictly increasing timestamps
            self.last_ts = ts
            result = self.landmarker.detect_for_video(image, ts)
        else:
            result = self.landmarker.detect(image)

        faces = []
        count = len(result.face_landmarks)
        index = 0
        while index < count:
            points = result.face_landmarks[index]
            xs = []
            ys = []
            for p in points:
                xs.append(p.x)
                ys.append(p.y)
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            area = (x1 - x0) * w * (y1 - y0) * h
            sig = {"smile": 0.0, "jaw": 0.0, "brow": 0.0, "frown": 0.0}
            if index < len(result.face_blendshapes):
                sig = signals_from_blendshapes(result.face_blendshapes[index])
            yaw, pitch = 0.0, 0.0
            if index < len(result.facial_transformation_matrixes):
                yaw, pitch = head_pose(result.facial_transformation_matrixes[index])
            faces.append(Face((x0, y0, x1, y1), area, sig, yaw, pitch))
            index += 1
        faces.sort(key=lambda f: f.area, reverse=True)
        self.last_ms = (time.perf_counter() - started) * 1000.0
        return faces

    def close(self):
        self.landmarker.close()


def player_face(faces):
    """The player's face (largest), or None if there's no face or it's ambiguous (two similar sizes)."""
    if not faces:
        return None
    if len(faces) >= 2 and faces[1].area >= C.AMBIGUOUS_RATIO * faces[0].area:
        return None
    return faces[0]


def fist_over_face(box, hand):
    """True if the sword hand's blade base is inside the face box (+ margin)."""
    if hand is None or not hand.sword_visible:
        return False
    x0, y0, x1, y1 = box
    mx = (x1 - x0) * C.FIST_MARGIN
    my = (y1 - y0) * C.FIST_MARGIN
    bx, by = hand.blade_base
    return (x0 - mx) <= bx <= (x1 + mx) and (y0 - my) <= by <= (y1 + my)
