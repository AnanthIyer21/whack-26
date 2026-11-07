"""The rival thread: events in, GRIP-9000's voice and subtitles out.

Loop (never blocks for more than 50 ms, never touches the game's state):
  1. take the next event from shared.events (if any), update stats,
     ask the timing engine whether to speak
  2. ~20 times a second: tick the engine (bomb settle, pause timers, halfway),
     once a second also check for habit patterns; collect finished network jobs
  3. notice when a line has finished, so the engine can start its quiet gap

Where a line comes from, in order:
  1. a fresh PRE-FETCHED line (written by Claude and voiced a few seconds earlier)
  2. a LIVE Claude line for big moments (deadline 2.3 s, game over 3.0 s)
  3. the voiced BANK (always instant, always works offline)
Network work runs on a small worker pool; results come back through a queue.
"""

import concurrent.futures
import csv
import json
import os
import queue
import random
import threading
import time

import shared
from agent.claude_writer import ClaudeWriter, LiveTTS, NetHealth
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
SESSION_JSON = os.path.join(DATA_DIR, "session.json")

TICK = 0.05
PATTERN_EVERY = 1.0
LIVE_DEADLINE = 2.3          # Claude (~1.2 s) + Edward (~0.6 s) + margin; then bank
FINAL_DEADLINE = 3.0         # the game over screen shows "..." meanwhile
PREVOICE = True              # pre-fetched lines are voiced ahead too (17M characters available)
PREFETCH_EVERY = 2.0         # refresh one standby line this often (~30 Claude calls a minute)
PREFETCH_MAX_AGE = 10.0      # older standby lines are stale (stats have moved on)
INTRO_MAX_AGE = 900.0        # the next intro is written during game over; valid for 15 minutes
FINAL_WORDS = 28             # word budget for the game over roast
LINE_WORDS = 18              # word budget for every other Claude line
SESSION_MEMORY_HOURS = 3.0

# What each moment means, for Claude.
MOMENTS = {
    "intro": "a new run is starting; greet the player",
    "game_over": "the run just ended; give the final roast of the whole run",
    "bomb_hit": "the player just sliced a bomb and lost a life",
    "last_life": "the player just sliced a bomb and is down to their last life",
    "time_warning": "10 seconds left in the run",
    "streak_big": "the player is on a long streak of slices without missing",
    "streak_broken": "the player's streak just ended",
    "miss": "a fruit just fell off the bottom of the screen uncut",
    "halfway": "halfway through the run; give a state-of-the-match comment",
    "pattern": "you have noticed a habit in how they play; call it out",
}


def log(text):
    print("[rival] " + text)


class LatencyLog:
    """One row per spoken line: how long from the game event to the first audio."""

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        new = not os.path.exists(LATENCY_CSV)
        self.lock = threading.Lock()
        self.file = open(LATENCY_CSV, "a", newline="")
        self.writer = csv.writer(self.file)
        if new:
            self.writer.writerow(["wall_time", "key", "source", "spoken_as", "event_to_decision_ms",
                                  "decision_to_audio_ms", "event_to_audio_ms", "text"])

    def write(self, key, source, spoken_as, event_t, decided_t, audio_t, text):
        with self.lock:
            self.writer.writerow([time.strftime("%H:%M:%S"), key, source, spoken_as,
                                  round((decided_t - event_t) * 1000, 1),
                                  round((audio_t - decided_t) * 1000, 1),
                                  round((audio_t - event_t) * 1000, 1), text])
            self.file.flush()

    def close(self):
        self.file.close()


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, value):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path + ".part", "w") as f:
        json.dump(value, f)
    os.replace(path + ".part", path)


class Rival:
    def __init__(self, offline=False, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.stats = Stats()
        self.engine = TimingEngine(self.stats, rng=self.rng, log=self._engine_log)
        self.detector = PatternDetector()
        self.bank = Bank(rng=self.rng)
        self.voice = Voice(log=log)
        self.latency = LatencyLog()
        self.best_score = read_json(BEST_JSON, {}).get("best_score", 0)
        self.session = read_json(SESSION_JSON, {"runs": []}).get("runs", [])
        self.speaking_until = 0.0
        self.speaking = False

        # network side (None when offline or keys missing)
        self.health = None
        self.writer = None
        self.tts = None
        self.pool = None
        if not offline and os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ELEVENLABS_API_KEY"):
            self.health = NetHealth(log)
            self.writer = ClaudeWriter(self.health, log)
            self.tts = LiveTTS(self.health, log)
            self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="rival-net")
        else:
            log("offline: bank lines only" + ("" if offline else " (API keys missing in .env)"))
        self.results = queue.Queue()
        self.token = 0
        self.pending = None          # the live Claude line we're waiting for
        self.prefetched = {}         # key -> {"text", "sound", "made_t"}
        self.prefetch_busy = set()
        self.next_prefetch = 0.0

    def _engine_log(self, now, text):
        if os.environ.get("RIVAL_VERBOSE"):
            log(". " + text)

    def online(self):
        return self.writer is not None and not self.health.offline

    # ---------------------------------------------------------------- events

    def on_event(self, event, now):
        if event["type"] == shared.GAME_START:
            self.detector.reset()
            intro = self.prefetched.get("intro")
            self.prefetched = {}
            if intro is not None:
                self.prefetched["intro"] = intro
            self.pending = None
            if self.health is not None:
                self.health.reset_for_new_run()
        if event["type"] == shared.GAME_OVER:
            event = dict(event)
            self.previous_best = self.best_score
            if event["score"] > self.best_score:
                event["new_best"] = self.best_score > 0
                self.best_score = event["score"]
                write_json(BEST_JSON, {"best_score": self.best_score})
        self.stats.update(event)
        decision = self.engine.on_event(event, now)
        if decision is not None:
            decision.origin_t = event["t"]
        if event["type"] == shared.GAME_OVER:
            self._remember_run(event)
        self.speak(decision, now)
        if event["type"] == shared.GAME_OVER and self.online():
            # Write the next run's intro now, while the game over screen is up.
            self.prefetch_busy.add("intro")
            self.pool.submit(self._prefetch_job, "intro", "smug", self.stats.snapshot(now),
                             {"previous_run": self.session[-1]})

    def tick(self, now, check_patterns):
        self._collect_results(now)

        if self.pending is not None and now >= self.pending["deadline"]:
            decision = self.pending["decision"]
            self.pending = None
            log("Claude too slow for " + decision.key + ": bank line instead")
            self._say_bank(decision, now, "bank (Claude timed out)")

        patterns = None
        if check_patterns:
            patterns = self.detector.check(self.stats, now)
        decision = self.engine.tick(now, patterns)
        self.speak(decision, now)

        if self.speaking and now >= self.speaking_until and not self.voice.busy():
            self.speaking = False
            shared.rival_speaking.clear()
            self.engine.line_finished(now)

        self._maybe_prefetch(now)

    # -------------------------------------------------------------- speaking

    def speak(self, decision, decided_t):
        if decision is None:
            return
        if self.pending is not None:
            log("dropping pending Claude line (" + self.pending["decision"].key + ") for " + decision.key)
            self.pending = None

        # 1. pre-fetched line, if fresh
        ready = self.prefetched.get(decision.key)
        if ready is not None:
            del self.prefetched[decision.key]
            max_age = INTRO_MAX_AGE if decision.key == "intro" else PREFETCH_MAX_AGE
            if decided_t - ready["made_t"] <= max_age:
                self._play(decision, ready["text"], ready["sound"], decided_t, "prefetch (Claude, ready)")
                return

        # 2. live Claude for big moments (and the intro when we remember a previous run)
        live = decision.source == "claude" or (decision.key == "intro" and self._previous_run() is not None)
        if live and self.online():
            self.token += 1
            deadline = FINAL_DEADLINE if (decision.final or decision.key == "intro") else LIVE_DEADLINE
            self.pending = {"token": self.token, "decision": decision, "deadline": decided_t + deadline,
                            "decided_t": decided_t}
            self.engine.line_started(decision, deadline + 0.5, decided_t)   # hold the floor while we wait
            stats = self.stats.snapshot(decided_t)
            extra = self._details(decision)
            self.pool.submit(self._live_job, self.token, decision, stats, extra)
            return

        # 3. bank
        spoken_as = "bank" if decision.source == "bank" else "bank (" + ("offline" if live else decision.source) + ")"
        self._say_bank(decision, decided_t, spoken_as)

    def _say_bank(self, decision, decided_t, spoken_as):
        key = bank_key(decision.key, decision.mood, decision.vars)
        text = self.bank.pick(key, decision.vars)
        if text is None:
            log("no bank line for " + key + " " + str(decision.vars) + ": staying quiet")
            self.engine.line_finished(decided_t)
            return
        self._play(decision, text, None, decided_t, spoken_as, cached=True)

    def _play(self, decision, text, sound, decided_t, spoken_as, cached=False):
        if cached:
            duration = self.voice.say_cached(text, decision.mood, final=decision.final)
        else:
            duration = self.voice.say_sound(sound, text, decision.mood, final=decision.final)
        audio_t = time.monotonic()
        self.engine.line_started(decision, duration, audio_t)
        self.speaking = True
        self.speaking_until = audio_t + duration
        if decision.key == "pattern":
            self.detector.mark_spoken(decision.vars["pattern"])
        self.latency.write(decision.key, decision.source, spoken_as, decision.origin_t, decided_t, audio_t, text)
        ms = round((audio_t - decision.origin_t) * 1000)
        log(decision.mood.upper() + " " + decision.key + " via " + spoken_as
            + (" (cut-in)" if decision.interrupt else "") + ": " + text + "  [" + str(ms) + " ms]")

    # ------------------------------------------------------------ network jobs

    def _live_job(self, token, decision, stats, extra):
        words = FINAL_WORDS if decision.final else LINE_WORDS
        text = self.writer.write(MOMENTS.get(decision.key, decision.key), decision.mood, stats, extra, max_words=words)
        sound = None
        if text is not None:
            sound = self.tts.synth(text)
        self.results.put(("live", token, text, sound))

    def _prefetch_job(self, key, mood, stats, extra):
        text = self.writer.write(MOMENTS[key], mood, stats, extra, prefetch=(key != "intro"), max_words=LINE_WORDS)
        sound = None
        if text is not None and PREVOICE:
            sound = self.tts.synth(text)
        self.results.put(("prefetch", key, text, sound))

    def _collect_results(self, now):
        while True:
            try:
                kind, ident, text, sound = self.results.get_nowait()
            except queue.Empty:
                return
            if kind == "prefetch":
                self.prefetch_busy.discard(ident)
                if text is not None and (sound is not None or not PREVOICE):
                    self.prefetched[ident] = {"text": text, "sound": sound[0] if sound else None, "made_t": now}
                continue
            if self.pending is None or self.pending["token"] != ident:
                continue    # cancelled or timed out; ignore
            decision = self.pending["decision"]
            decided_t = self.pending["decided_t"]
            self.pending = None
            if text is None or sound is None:
                self._say_bank(decision, decided_t, "bank (Claude/voice failed)")
            else:
                self._play(decision, text, sound[0], decided_t, "Claude live")

    def _maybe_prefetch(self, now):
        if not self.online() or now < self.next_prefetch:
            return
        if not self.stats.running or self.stats.paused or self.stats.over:
            return
        self.next_prefetch = now + PREFETCH_EVERY
        wanted = ["miss"]
        if self.stats.current_streak >= 4:
            wanted.append("streak_broken")
        if self.stats.lives >= 3:
            wanted.append("bomb_hit")
        elif self.stats.lives == 2:
            wanted.append("last_life")
        # refresh the stalest standby line that isn't already being written
        choice = None
        choice_age = -1.0
        for key in wanted:
            if key in self.prefetch_busy:
                continue
            ready = self.prefetched.get(key)
            age = 999.0 if ready is None else now - ready["made_t"]
            if age > choice_age:
                choice = key
                choice_age = age
        if choice is None or choice_age < PREFETCH_MAX_AGE / 2.0:
            return
        moods = {"miss": "gloating", "streak_broken": "gloating", "bomb_hit": "gloating", "last_life": "gloating"}
        stats = self.stats.snapshot(now)
        extra = {}
        if choice in ("bomb_hit", "last_life"):
            extra["lives_after_this_bomb"] = self.stats.lives - 1
        if choice == "streak_broken":
            extra["streak_that_ends"] = self.stats.current_streak
        if choice == "miss":
            extra["note"] = "you don't know which side it fell on; don't mention a side"
        self.prefetch_busy.add(choice)
        self.pool.submit(self._prefetch_job, choice, moods[choice], stats, extra)

    # ----------------------------------------------------------------- memory

    def _previous_run(self):
        if not self.session:
            return None
        last = self.session[-1]
        if time.time() - last.get("wall_time", 0) > SESSION_MEMORY_HOURS * 3600:
            return None
        return last

    def _details(self, decision):
        extra = {}
        for key in decision.vars:
            extra[key] = decision.vars[key]
        previous = self._previous_run()
        if decision.key == "game_over":
            extra["previous_best"] = getattr(self, "previous_best", 0)
            worst = "left" if self.stats.misses["left"] > self.stats.misses["right"] else "right"
            extra["side_missed_most"] = worst
            # the run we just saved is session[-1]; compare with the one before it
            if len(self.session) >= 2:
                before = self.session[-2]
                if time.time() - before.get("wall_time", 0) <= SESSION_MEMORY_HOURS * 3600:
                    extra["previous_run"] = before
        elif previous is not None and decision.key in ("intro", "halfway"):
            extra["previous_run"] = previous
        return extra

    def _remember_run(self, event):
        run = {
            "wall_time": time.time(),
            "score": event["score"],
            "reason": event["reason"],
            "bombs_hit": self.stats.bombs,
            "misses_left": self.stats.misses["left"],
            "misses_right": self.stats.misses["right"],
            "best_streak": self.stats.best_streak,
            "pauses": sum(self.stats.pauses.values()),
        }
        self.session.append(run)
        self.session = self.session[-20:]
        write_json(SESSION_JSON, {"runs": self.session})

    def close(self):
        self.voice.stop()
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
        self.latency.close()


def run(stop_event, offline=False):
    rival = Rival(offline=offline)
    if rival.voice.wait_for_mixer(stop_event):
        threading.Thread(target=rival.voice.preload, args=(stop_event,), name="rival-preload", daemon=True).start()
        if rival.tts is not None:
            rival.pool.submit(rival.tts.warm_up)
    log("GRIP-9000 ready (" + str(len(rival.voice.lines)) + " bank lines, "
        + ("Claude + live voice on" if rival.online() else "offline") + ")")
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
