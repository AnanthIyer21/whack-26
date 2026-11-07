"""GRIP-9000's mouth: plays lines on the reserved voice channel and sends subtitles.

The game owns the mixer (it calls pre_init with the shared constants and reserves
channel 0). The rival only plays Sounds on channel 0. If the mixer isn't running
(e.g. a game build without sound), lines become subtitle-only so nothing breaks.

Bank clips are decoded into memory in the background at startup, so playing one
is just Channel.play(): well under a millisecond.
"""

import json
import os
import threading
import time

import shared

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "assets", "voice", "cache")
MANIFEST = os.path.join(CACHE_DIR, "manifest.json")
SUBTITLE_PAD = 0.5          # bubble stays up this long after the audio ends
WORDS_PER_SECOND = 2.7      # for estimating subtitle-only durations


class Voice:
    def __init__(self, log=print):
        self.log = log
        self.lines = {}
        if os.path.exists(MANIFEST):
            with open(MANIFEST) as f:
                self.lines = json.load(f).get("lines", {})
        self.sounds = {}
        self.sounds_lock = threading.Lock()
        self.channel = None
        self.current_text = None

    # ---------------------------------------------------------------- set-up

    def mixer_ready(self):
        try:
            import pygame
            return pygame.mixer.get_init() is not None
        except Exception:
            return False

    def wait_for_mixer(self, stop_event, timeout=5.0):
        """The game initialises the mixer on its own thread; wait briefly for it."""
        deadline = time.monotonic() + timeout
        while not stop_event.is_set() and time.monotonic() < deadline:
            if self.mixer_ready():
                import pygame
                self.channel = pygame.mixer.Channel(shared.VOICE_CHANNEL)
                return True
            stop_event.wait(0.05)
        self.log("mixer not initialised by the game: subtitles only")
        return False

    def preload(self, stop_event):
        """Decode every bank clip into memory (background thread)."""
        import pygame
        started = time.monotonic()
        count = 0
        for text in list(self.lines):
            if stop_event.is_set():
                return
            self._sound_for(text, pygame)
            count += 1
        self.log("preloaded " + str(count) + " clips in " + str(round(time.monotonic() - started, 1)) + " s")

    def _sound_for(self, text, pygame):
        with self.sounds_lock:
            sound = self.sounds.get(text)
        if sound is not None:
            return sound
        entry = self.lines.get(text)
        if entry is None:
            return None
        sound = pygame.mixer.Sound(os.path.join(CACHE_DIR, entry["file"]))
        with self.sounds_lock:
            self.sounds[text] = sound
        return sound

    # -------------------------------------------------------------- speaking

    def say_cached(self, text, mood, final=False):
        """Play a bank line now (cutting off anything playing). Returns its duration in s."""
        duration = None
        if self.channel is not None:
            import pygame
            sound = self._sound_for(text, pygame)
            if sound is not None:
                self.channel.stop()
                self.channel.play(sound)
                duration = sound.get_length()
        if duration is None:
            duration = max(1.5, len(text.split()) / WORDS_PER_SECOND)
        self.current_text = text
        shared.rival_speaking.set()
        shared.post_rival_line(text, mood, duration + SUBTITLE_PAD, final=final)
        return duration

    def busy(self):
        if self.channel is not None:
            return self.channel.get_busy()
        return False

    def stop(self):
        if self.channel is not None:
            self.channel.stop()
        shared.rival_speaking.clear()
