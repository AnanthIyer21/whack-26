"""MediaPipe Hand Landmarker (pretrained, Google) wrapper.

VIDEO mode: detect() is synchronous on our own thread, so we can time it
exactly and we always know which frame a result belongs to.
"""
from dataclasses import dataclass

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision as mp_vision

from vision import config


@dataclass
class DetectedHand:
    img: np.ndarray      # (21, 3) normalised image coords: x, y in 0..1 (mirrored frame), z relative depth
    world: np.ndarray    # (21, 3) metric 3D coords (metres, origin near hand centre)
    label: str           # "Left" or "Right" (the person's actual hand)
    score: float         # handedness confidence 0..1


class HandTracker:
    def __init__(self, model_path=config.MODEL_PATH, max_hands=config.MAX_HANDS):
        opts = mp_vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=config.MIN_DETECTION_CONF,
            min_hand_presence_confidence=config.MIN_PRESENCE_CONF,
            min_tracking_confidence=config.MIN_TRACKING_CONF,
        )
        self._lm = mp_vision.HandLandmarker.create_from_options(opts)
        self._last_ts = -1

    def detect(self, rgb, t):
        """rgb: mirrored (H, W, 3) uint8. t: time.monotonic() seconds."""
        ts = int(t * 1000)
        if ts <= self._last_ts:          # MediaPipe needs strictly increasing timestamps
            ts = self._last_ts + 1
        self._last_ts = ts
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._lm.detect_for_video(image, ts)
        hands = []
        for i, lms in enumerate(res.hand_landmarks):
            img = np.array([(p.x, p.y, p.z) for p in lms], dtype=np.float32)
            wl = res.hand_world_landmarks[i]
            world = np.array([(p.x, p.y, p.z) for p in wl], dtype=np.float32)
            cat = res.handedness[i][0]
            label = cat.category_name
            if config.FLIP_HANDEDNESS:
                label = "Left" if label == "Right" else "Right"
            hands.append(DetectedHand(img, world, label, float(cat.score)))
        return dedupe(hands)

    def close(self):
        self._lm.close()


def dedupe(hands, min_dist=config.DEDUPE_WRIST_DIST):
    """Drop a detection whose wrist sits on top of an earlier (higher-score) one."""
    hands = sorted(hands, key=lambda h: -h.score)
    kept = []
    for h in hands:
        if all(np.linalg.norm(h.img[0, :2] - k.img[0, :2]) >= min_dist for k in kept):
            kept.append(h)
    return kept


# Skeleton for drawing (pairs of landmark indices).
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (5, 9), (9, 10), (10, 11), (11, 12),       # middle
    (9, 13), (13, 14), (14, 15), (15, 16),     # ring
    (13, 17), (17, 18), (18, 19), (19, 20),    # pinky
    (0, 17),
]
