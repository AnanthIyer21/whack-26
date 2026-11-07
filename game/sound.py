"""Sound effects. Placeholders are synthesised in code at startup; a file at
assets/sfx/<name>.wav or .ogg (RB's) replaces the placeholder automatically.

Never raises: if there's no audio device the game just runs silently. Volumes are
kept low so the rival's voice stays clear. M mutes.
"""
import math
import os
import random
from array import array

import pygame

from game import assets

RATE = 22050
enabled = False
muted = False
_sounds = {}
_loop_channel = None
VOLUME = {"swoosh": 0.35, "slice": 0.55, "draw": 0.4, "sheathe": 0.25, "fuse": 0.25, "boom": 0.9,
          "combo": 0.5, "streak": 0.45, "beep": 0.4, "go": 0.5, "life_lost": 0.5, "game_over": 0.6, "pause": 0.35}


def pre_init():
    """Call before pygame.init() so audio starts in our format with low latency."""
    pygame.mixer.pre_init(RATE, -16, 1, 512)


def init():
    global enabled, RATE
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(RATE, -16, 1, 512)
        RATE = pygame.mixer.get_init()[0]     # synthesise at whatever rate the device really runs
        pygame.mixer.set_num_channels(24)
        enabled = True
    except pygame.error as e:
        print(f"[sound] no audio ({e}); running silently")
        enabled = False
        return
    for name in VOLUME:
        _sounds[name] = _load(name)


def _load(name):
    for ext in ("wav", "ogg"):
        path = os.path.join(assets.ROOT, "sfx", f"{name}.{ext}")
        if os.path.exists(path):
            try:
                return pygame.mixer.Sound(path)
            except pygame.error as e:
                print(f"[sound] couldn't load {path}: {e}")
    return _make(SYNTH[name]())


def play(name, volume=1.0):
    if not enabled or muted or name not in _sounds:
        return
    s = _sounds[name]
    s.set_volume(VOLUME.get(name, 0.5) * volume)
    s.play()


def set_fuse(on):
    """Fizzing fuse loop while a bomb is on screen."""
    global _loop_channel
    if not enabled:
        return
    if on and not muted and (_loop_channel is None or not _loop_channel.get_busy()):
        _sounds["fuse"].set_volume(VOLUME["fuse"])
        _loop_channel = _sounds["fuse"].play(loops=-1)
    elif (not on or muted) and _loop_channel is not None:
        _loop_channel.stop()
        _loop_channel = None


def toggle_mute():
    global muted
    muted = not muted
    if muted:
        set_fuse(False)
    print(f"[sound] {'muted' if muted else 'unmuted'}")


# ---------------- synthesis (pure Python, a fraction of a second at startup) ----------------
def _make(samples):
    channels = pygame.mixer.get_init()[2]
    data = array("h", (max(-32767, min(32767, int(v * 32767))) for v in samples))
    if channels == 2:
        st = array("h")
        for v in data:
            st.append(v)
            st.append(v)
        data = st
    return pygame.mixer.Sound(buffer=data.tobytes())


def _n(sec):
    return int(RATE * sec)


def _env(i, n, attack=0.01, power=2.0):
    a = _n(attack)
    if i < a:
        return i / max(1, a)
    return (1 - (i - a) / max(1, n - a)) ** power


def _swoosh():
    n, out, lp = _n(0.18), [], 0.0
    for i in range(n):
        k = i / n
        lp += (random.uniform(-1, 1) - lp) * (0.08 + 0.5 * math.sin(math.pi * k))  # filter opens then closes
        out.append(lp * math.sin(math.pi * k) * 0.9)
    return out


def _slice():
    n, out, lp = _n(0.22), [], 0.0
    for i in range(n):
        t = i / RATE
        lp += (random.uniform(-1, 1) - lp) * 0.35
        thump = math.sin(2 * math.pi * (180 - 400 * t) * t) * 0.6
        out.append((lp * 0.8 + thump) * _env(i, n, 0.003, 3))
    return out


def _draw():
    n, out = _n(0.35), []
    for i in range(n):
        t = i / RATE
        f = 2400 + 1800 * t
        v = math.sin(2 * math.pi * f * t) * 0.4 + math.sin(2 * math.pi * f * 1.51 * t) * 0.25
        v += random.uniform(-1, 1) * 0.15 * max(0, 1 - t * 8)
        out.append(v * _env(i, n, 0.005, 2.5))
    return out


def _sheathe():
    n, out, lp = _n(0.15), [], 0.0
    for i in range(n):
        lp += (random.uniform(-1, 1) - lp) * 0.1
        out.append(lp * _env(i, n, 0.02, 1.5))
    return out


def _fuse():
    n, out = _n(0.5), []
    for i in range(n):
        crackle = random.uniform(-1, 1) if random.random() < 0.08 else random.uniform(-0.15, 0.15)
        out.append(crackle * 0.5)
    return out


def _boom():
    n, out, lp, lp2 = _n(1.3), [], 0.0, 0.0
    for i in range(n):
        t = i / RATE
        lp += (random.uniform(-1, 1) - lp) * 0.06
        lp2 += (lp - lp2) * 0.2
        sub = math.sin(2 * math.pi * (70 - 30 * t) * t)
        out.append((lp2 * 4.0 + sub * 0.7) * _env(i, n, 0.004, 2.2))
    return out


def _tones(freqs, each, gap=0.0, wave=1.0):
    out = []
    for f in freqs:
        n = _n(each)
        for i in range(n):
            t = i / RATE
            v = math.sin(2 * math.pi * f * t) + 0.3 * wave * math.sin(4 * math.pi * f * t)
            out.append(v * 0.45 * _env(i, n, 0.005, 2))
        out += [0.0] * _n(gap)
    return out


def _combo():
    return _tones([660, 880, 1320], 0.12)


def _streak():
    return _tones([880, 1175, 1568], 0.1)


def _beep():
    return _tones([660], 0.15)


def _go():
    return _tones([1320], 0.35)


def _life_lost():
    n, out = _n(0.4), []
    for i in range(n):
        t = i / RATE
        out.append(math.sin(2 * math.pi * (420 - 300 * t) * t) * 0.5 * _env(i, n, 0.01, 1.5))
    return out


def _game_over():
    return _tones([392, 370, 349, 262], 0.28, 0.02, wave=2.0)


def _pause():
    return _tones([523, 392], 0.1)


SYNTH = {"swoosh": _swoosh, "slice": _slice, "draw": _draw, "sheathe": _sheathe, "fuse": _fuse, "boom": _boom,
         "combo": _combo, "streak": _streak, "beep": _beep, "go": _go, "life_lost": _life_lost,
         "game_over": _game_over, "pause": _pause}
