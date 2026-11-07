"""Network side of GRIP-9000: Claude writes a line, ElevenLabs voices it.

Both run on worker threads (never on the rival loop). Each returns None on any
failure, so the caller simply falls back to a bank line. Repeated network
failures switch the rival to offline mode for the rest of the run.
"""

import json
import os
import threading
import time

import anthropic
import numpy as np
from elevenlabs.client import ElevenLabs

from agent.persona import PREFETCH_NOTE, SYSTEM_PROMPT, filter_line

CLAUDE_MODEL = "claude-haiku-5-5"
LIVE_MODEL = "eleven_flash_v2_5"
PCM_RATE = 22050
MAX_TOKENS = 60
FAILURES_TO_GO_OFFLINE = 3
FAILURE_WINDOW = 30.0


class NetHealth:
    """Counts network failures; 3 within 30 s means 'go offline'."""

    def __init__(self, log):
        self.log = log
        self.lock = threading.Lock()
        self.failures = []
        self.offline = False

    def failed(self, what, error):
        now = time.monotonic()
        with self.lock:
            recent = []
            for t in self.failures:
                if now - t < FAILURE_WINDOW:
                    recent.append(t)
            recent.append(now)
            self.failures = recent
            self.log(what + " failed (" + type(error).__name__ + ": " + str(error)[:120] + ")")
            if len(recent) >= FAILURES_TO_GO_OFFLINE and not self.offline:
                self.offline = True
                self.log("3 network failures in 30 s: OFFLINE mode (bank lines only) for this run")

    def reset_for_new_run(self):
        with self.lock:
            self.failures = []
            self.offline = False


class ClaudeWriter:
    def __init__(self, health, log):
        self.health = health
        self.log = log
        self.client = anthropic.Anthropic(timeout=3.0, max_retries=0)

    def write(self, moment, mood, stats, extra=None, prefetch=False, max_words=18):
        """One spoken line from Claude, filtered. None if it fails or is rejected."""
        if self.health.offline:
            return None
        clean = {}
        for key in stats:
            value = stats[key]
            if value is None or value == [] or value == "":
                continue
            clean[key] = value
        parts = ["moment: " + moment, "your_mood: " + mood, "stats: " + json.dumps(clean, separators=(",", ":"))]
        if extra:
            parts.append("details: " + json.dumps(extra, separators=(",", ":")))
        if prefetch:
            parts.append(PREFETCH_NOTE)
        parts.append("Reply in at most " + str(max_words) + " words.")
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "disabled"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": "\n".join(parts)}],
            )
        except Exception as exc:
            self.health.failed("Claude", exc)
            return None
        if response.stop_reason == "refusal":
            self.log("Claude refused a line for " + moment)
            return None
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text
        line = filter_line(text, max_words)
        if line is None:
            self.log("Claude line rejected by filter (" + str(len(text.split())) + " words): " + repr(text[:160]))
        return line


class LiveTTS:
    """ElevenLabs Flash -> a pygame Sound ready to play (whole clip, ~0.5 s for a long line)."""

    def __init__(self, health, log):
        self.health = health
        self.log = log
        self.voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
        self.client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY", ""))

    def warm_up(self):
        """Opens the HTTPS connection early so the first real line isn't slower."""
        self.synth("Ready.")

    def synth(self, text):
        """Returns (pygame Sound, seconds) or None."""
        if self.health.offline or not self.voice_id:
            return None
        try:
            pcm = bytearray()
            for chunk in self.client.text_to_speech.stream(
                voice_id=self.voice_id, text=text, model_id=LIVE_MODEL,
                output_format="pcm_" + str(PCM_RATE), optimize_streaming_latency=3,
            ):
                pcm.extend(chunk)
        except Exception as exc:
            self.health.failed("ElevenLabs", exc)
            return None
        if len(pcm) < 2:
            return None
        return pcm_to_sound(bytes(pcm))


def pcm_to_sound(pcm):
    """22,050 Hz mono 16-bit -> the game's 44,100 Hz stereo 16-bit mixer format."""
    import pygame
    if pygame.mixer.get_init() is None:
        return None
    if len(pcm) % 2:
        pcm = pcm[:-1]
    mono = np.frombuffer(pcm, dtype=np.int16)
    upsampled = np.repeat(mono, 2)                      # exact 2x: 22,050 -> 44,100 Hz
    stereo = np.ascontiguousarray(np.column_stack((upsampled, upsampled)))
    sound = pygame.sndarray.make_sound(stereo)
    return sound, len(mono) / float(PCM_RATE)
