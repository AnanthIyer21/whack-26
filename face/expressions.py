"""Turns per-frame face signals into held expressions and one-off 'fired' events.

Pure logic (no camera, no MediaPipe), so every rule is testable with made-up numbers.

The idea, per expression:
  level    = how far the (smoothed) signal is above its threshold; >= 0 means "on"
  held     = on continuously for at least HOLD seconds
  fire     = held AND armed -> one face event, then disarmed
  re-arm   = level drops below -RELEASE_GAP (hysteresis: one long smile fires once)

Thresholds are relative to the player's own baseline (their resting face), which
is a rolling 20th percentile of the last 20 s, so a naturally smiley face isn't
"smiling" all the time. Head pose baseline is the median (their usual position).
"""

from collections import deque

import numpy as np

from face import config as C

SIGNALS = ("smile", "jaw", "brow", "frown")


class Calibrator:
    """Rolling per-player baseline of every signal, plus the 5 s warm-up."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.samples = deque()      # (t, smile, jaw, brow, frown, yaw, pitch)
        self.first_t = None
        self.cache_t = None
        self.cache = None

    def add(self, t, sig, yaw, pitch):
        if self.first_t is None:
            self.first_t = t
        self.samples.append((t, sig["smile"], sig["jaw"], sig["brow"], sig["frown"], yaw, pitch))
        while self.samples and t - self.samples[0][0] > C.BASELINE_WINDOW:
            self.samples.popleft()

    def calibrated(self, t):
        return self.first_t is not None and t - self.first_t >= C.WARMUP

    def baseline(self, t):
        """{'smile','jaw','brow','frown': resting level, 'yaw','pitch': usual head position}."""
        if self.cache_t == t and self.cache is not None:
            return self.cache
        if not self.samples:
            base = {"smile": 0.0, "jaw": 0.0, "brow": 0.0, "frown": 0.0, "yaw": 0.0, "pitch": 0.0}
        else:
            arr = np.array(self.samples, dtype=float)
            base = {}
            index = 1
            for name in SIGNALS:
                base[name] = float(np.percentile(arr[:, index], C.BASELINE_PERCENTILE))
                index += 1
            base["yaw"] = float(np.median(arr[:, 5]))
            base["pitch"] = float(np.median(arr[:, 6]))
        self.cache_t = t
        self.cache = base
        return base


def levels(sig, yaw_rel, pitch_rel, base):
    """How far above its threshold each expression is (>= 0 means on). Pose levels are in degrees / 100."""
    smile = sig["smile"]
    jaw = sig["jaw"]
    out = {}
    out["smiling"] = smile - max(C.SMILE_MIN, base["smile"] + C.SMILE_MARGIN)
    out["laughing"] = min(smile - max(C.LAUGH_SMILE, base["smile"] + C.LAUGH_SMILE_MARGIN),
                          jaw - max(C.LAUGH_JAW, base["jaw"] + C.LAUGH_JAW_MARGIN))
    out["shock"] = min(jaw - max(C.SHOCK_JAW, base["jaw"] + C.SHOCK_MARGIN), C.SHOCK_MAX_SMILE - smile)
    brow_level = sig["brow"] - max(C.FROWN_BROW, base["brow"] + C.FROWN_BROW_MARGIN)
    mouth_level = sig["frown"] - C.FROWN_MOUTH
    out["frowning"] = min(max(brow_level, mouth_level), C.FROWN_MAX_SMILE - smile)
    out["looking_away"] = max(abs(yaw_rel) - C.AWAY_YAW, abs(pitch_rel) - C.AWAY_PITCH) / 100.0
    return out


class ExpressionTracker:
    """Smoothing, hold times, hysteresis and priority for one player's face."""

    def __init__(self):
        self.calibrator = Calibrator()
        self.reset()

    def reset(self):
        self.calibrator.reset()
        self.smoothed = None
        self.held_since = {}
        self.armed = {}
        for name in C.PRIORITY:
            self.held_since[name] = None
            self.armed[name] = True
        self.current = "neutral"
        self.last_levels = {}
        self.last_yaw = 0.0
        self.last_pitch = 0.0
        self.last_update_t = None

    def interrupt(self):
        """A frame we couldn't read (fist over the face, ambiguous faces): the hold PAUSES.

        If reading resumes within MAX_PAUSE, holds carry on; a longer gap resets them (in update)."""
        self.current = "neutral"

    def update(self, t, raw, yaw, pitch):
        """One readable frame. raw: {'smile','jaw','brow','frown'} 0..1; yaw/pitch in degrees (absolute).

        Returns (current_expression, fired) where fired is (expression, strength) or None.
        """
        if self.last_update_t is not None and t - self.last_update_t > C.MAX_PAUSE:
            for name in C.PRIORITY:
                self.held_since[name] = None     # unreadable for too long: holds start again
        self.last_update_t = t
        if self.smoothed is None:
            self.smoothed = dict(raw)
            self.smoothed["yaw"] = yaw
            self.smoothed["pitch"] = pitch
        else:
            a = C.SMOOTHING
            for name in SIGNALS:
                self.smoothed[name] += a * (raw[name] - self.smoothed[name])
            self.smoothed["yaw"] += a * (yaw - self.smoothed["yaw"])
            self.smoothed["pitch"] += a * (pitch - self.smoothed["pitch"])

        sig = {}
        for name in SIGNALS:
            sig[name] = self.smoothed[name]
        self.calibrator.add(t, sig, self.smoothed["yaw"], self.smoothed["pitch"])
        base = self.calibrator.baseline(t)
        yaw_rel = self.smoothed["yaw"] - base["yaw"]
        pitch_rel = self.smoothed["pitch"] - base["pitch"]
        self.last_yaw = yaw_rel
        self.last_pitch = pitch_rel
        lv = levels(sig, yaw_rel, pitch_rel, base)
        self.last_levels = lv

        held = []
        for name in C.PRIORITY:
            level = lv[name]
            if level >= 0:
                if self.held_since[name] is None:
                    self.held_since[name] = t
                if t - self.held_since[name] >= C.HOLD[name]:
                    held.append(name)
            elif level >= -C.HOLD_SLACK and self.held_since[name] is not None:
                # Hovering just under the line: keep the hold going (don't restart it).
                if t - self.held_since[name] >= C.HOLD[name]:
                    held.append(name)
            else:
                self.held_since[name] = None
                if level < -C.RELEASE_GAP:
                    self.armed[name] = True

        self.current = "neutral"
        for name in held:
            if name in C.ENABLED_EXPRESSIONS:
                self.current = name
                break

        if not self.calibrator.calibrated(t):
            return self.current, None

        fired = None
        higher_active = False
        for name in C.PRIORITY:
            if name not in C.ENABLED_EXPRESSIONS:
                continue
            if higher_active:
                # A higher-priority expression is on (e.g. laughing): this one (smiling) is part of it,
                # so it's used up rather than firing a second heckle a moment later.
                if lv[name] >= 0:
                    self.armed[name] = False
                continue
            if lv[name] >= 0:
                higher_active = True
                if name in held and self.armed[name]:
                    strength = min(1.0, max(0.0, lv[name] / 0.3 + 0.5))
                    fired = (name, strength)
                    self.armed[name] = False
        return self.current, fired

    def calibrated(self, t):
        return self.calibrator.calibrated(t)
