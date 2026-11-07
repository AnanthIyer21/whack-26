"""The rival thread: events in, GRIP-9000's voice and subtitles out.

Loop (never blocks for more than 50 ms, never touches the game's state):
  1. take the next event from shared.events (if any), update stats,
     ask the timing engine whether to speak
  2. ~20 times a second: tick the engine (bomb settle, pause timers, halfway),
     once a second also check for habit patterns
  3. notice when a line has finished, so the engine can start its quiet gap

Milestone 2: every line comes from the voiced bank. Claude moments use their
bank fallback for now; the Claude writer plugs in at milestone 4.
"""

import csv
import json
import os
import queue
import random
import threading
import time

import shared
from agent.lines import Bank, bank_key
from agent.patterns import PatternDetector
from agent.stats import Stats
from agent.timing import TimingEngine
from agent.voice import Voice

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
DATA_DIR = os.path.join(ROOT, "data")
LATENCY_CSV = os.path.join(LOG_DIR, "latency.csv")
BEST_JSON = os.path.join(DATA_DIR, "best.json")
TICK = 0.05
PATTERN_EVERY = 1.0


def log(text):
    print("[rival] " + text)


class LatencyLog:
    """One row per spoken line: how long from the game event to the first audio."""

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        new = not os.path.exists(LATENCY_CSV)
        self.file = open(LATENCY_CSV, "a", newline="")
        self.writer = csv.writer(self.file)
        if new:
            self.writer.writerow(["wall_time", "key", "source", "spoken_as", "event_to_decision_ms",
                                  "decision_to_audio_ms", "event_to_audio_ms", "text"])

    def write(self, key, source, spoken_as, event_t, decided_t, audio_t, text):
        self.writer.writerow([time.strftime("%H:%M:%S"), key, source, spoken_as,
                              round((decided_t - event_t) * 1000, 1),
                              round((audio_t - decided_t) * 1000, 1),
                              round((audio_t - event_t) * 1000, 1), text])
        self.file.flush()

    def close(self):
        self.file.close()


def load_best():
    try:
        with open(BEST_JSON) as f:
            return json.load(f).get("best_score", 0)
    except Exception:
        return 0


def save_best(score):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BEST_JSON, "w") as f:
        json.dump({"best_score": score}, f)


class Rival:
    def __init__(self, offline=False, rng=None):
        self.offline = offline
        self.rng = rng if rng is not None else random.Random()
        self.stats = Stats()
        self.engine = TimingEngine(self.stats, rng=self.rng, log=self._engine_log)
        self.detector = PatternDetector()
        self.bank = Bank(rng=self.rng)
        self.voice = Voice(log=log)
        self.latency = LatencyLog()
        self.best_score = load_best()
        self.speaking_until = 0.0
        self.speaking = False

    def _engine_log(self, now, text):
        if os.environ.get("RIVAL_VERBOSE"):
            log(". " + text)

    # ---------------------------------------------------------------- events

    def on_event(self, event, now):
        if event["type"] == shared.GAME_OVER:
            event = dict(event)
            if event["score"] > self.best_score and self.stats.runs_this_session >= 1:
                event["new_best"] = self.best_score > 0
                self.best_score = event["score"]
                save_best(self.best_score)
        self.stats.update(event)
        if event["type"] == shared.GAME_START:
            self.detector.reset()
        decision = self.engine.on_event(event, now)
        if decision is not None:
            decision.origin_t = event["t"]
        self.speak(decision, now)

    def tick(self, now, check_patterns):
        patterns = None
        if check_patterns:
            patterns = self.detector.check(self.stats, now)
        decision = self.engine.tick(now, patterns)
        self.speak(decision, now)

        if self.speaking and now >= self.speaking_until and not self.voice.busy():
            self.speaking = False
            shared.rival_speaking.clear()
            self.engine.line_finished(now)

    # -------------------------------------------------------------- speaking

    def speak(self, decision, decided_t):
        if decision is None:
            return
        event_t = decision.origin_t
        key = bank_key(decision.key, decision.mood, decision.vars)
        text = self.bank.pick(key, decision.vars)
        if text is None:
            log("no bank line for " + key + " " + str(decision.vars) + ": staying quiet")
            self.engine.line_finished(decided_t)
            return
        duration = self.voice.say_cached(text, decision.mood, final=decision.final)
        audio_t = time.monotonic()
        self.engine.line_started(decision, duration, audio_t)
        self.speaking = True
        self.speaking_until = audio_t + duration
        if decision.key == "pattern":
            self.detector.mark_spoken(decision.vars["pattern"])
        spoken_as = "bank" if decision.source == "bank" else "bank (fallback for " + decision.source + ")"
        self.latency.write(decision.key, decision.source, spoken_as, event_t, decided_t, audio_t, text)
        ms = round((audio_t - event_t) * 1000)
        log(decision.mood.upper() + " " + decision.key + (" (cut-in)" if decision.interrupt else "")
            + ": " + text + "  [" + str(ms) + " ms]")

    def close(self):
        self.voice.stop()
        self.latency.close()


def run(stop_event, offline=False):
    rival = Rival(offline=offline)
    if rival.voice.wait_for_mixer(stop_event):
        threading.Thread(target=rival.voice.preload, args=(stop_event,), name="rival-preload", daemon=True).start()
    log("GRIP-9000 ready (" + str(len(rival.voice.lines)) + " bank lines" + (", offline" if offline else "") + ")")
    next_pattern = 0.0
    try:
        while not stop_event.is_set():
            try:
                event = shared.events.get(timeout=TICK)
            except queue.Empty:
                event = None
            now = time.monotonic()
            if event is not None:
                rival.on_event(event, now)
            check = now >= next_pattern
            if check:
                next_pattern = now + PATTERN_EVERY
            rival.tick(now, check)
    finally:
        rival.close()
