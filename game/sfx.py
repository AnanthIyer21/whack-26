"""Game sound effects and music (RBadiadka7). Files and names: assets/MANIFEST.md.

Hooked in at three places, nothing else needs to know about it:
  - game/events.py   Emitter.emit -> sfx.on_event(type_)   (slice, bomb_hit, combo, ...)
  - game/app.py      every frame  -> sfx.update(app)       (music per scene, ducking, Sound On/Off)
  - game/scenes/play.py countdown -> sfx.countdown(prev, cd, total)   (3-2-1 beeps)

Rules: never touches channel 0 (GRIP-9000's voice, reserved by app.py); everything is
multiplied by shared.DUCK_LEVEL while shared.rival_speaking is set; any missing file,
missing audio device or mixer error just means silence, never a crash.
"""
import os
import random

import pygame

import shared

try:
    from .boom import WINDUP as BOMB_DELAY   # the visual boom comes after the bomb's wind-up
except ImportError:
    BOMB_DELAY = 0.45

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")

SFX_VOLUME = 0.7
MUSIC_VOLUME = 0.35
MUSIC_FADE_MS = 600
STING_GAP = 1.2          # seconds of quiet after game over so the sting (and the roast) land

# event type -> list of sound names (one picked at random) ; extra layers in LAYERS
EVENT_SOUNDS = {
    "slice": ["sfx_slice_1", "sfx_slice_2", "sfx_slice_3"],
    "sword_drawn": ["sfx_sword_draw"],
    "sword_sheathed": ["sfx_sword_sheathe"],
    "combo": ["sfx_combo"],
    "streak": ["sfx_streak"],
    "game_start": ["sfx_countdown_go"],
    "resume": ["sfx_countdown_go"],
    "game_over": ["sfx_game_over"],
}
LAYERS = {"slice": ["sfx_splat"]}
MUSIC = {"play": "music_game.ogg", "menu": "music_menu.ogg"}

_sounds = {}
_loaded = False
_enabled = True
_duck = 1.0
_music_now = None        # which track is playing: "play" / "menu" / None
_quiet_until = 0.0       # no music before this time (after game over)
_scheduled = []          # [(time, sound name)] for sounds that must wait (the explosion)


def _now():
    return pygame.time.get_ticks() / 1000


def _ready():
    try:
        return pygame.mixer.get_init() is not None
    except pygame.error:
        return False


def _load():
    global _loaded
    if _loaded or not _ready():
        return
    _loaded = True
    names = {n for v in EVENT_SOUNDS.values() for n in v} | {n for v in LAYERS.values() for n in v}
    names |= {"sfx_countdown_beep"}
    for n in names:
        try:
            _sounds[n] = pygame.mixer.Sound(os.path.join(ASSETS, n + ".ogg"))
        except (pygame.error, FileNotFoundError):
            pass                              # missing file: that sound is silent


def play(name):
    """Play one sound on any free channel except the rival's."""
    if not _enabled:
        return
    _load()
    snd = _sounds.get(name)
    if snd is None:
        return
    try:
        snd.set_volume(SFX_VOLUME * _duck)
        ch = pygame.mixer.find_channel(True)  # force=True: steal the oldest if all are busy
        if ch is not None and ch.id != shared.VOICE_CHANNEL:
            ch.play(snd)
    except pygame.error:
        pass


def on_event(type_):
    """Called for every game -> rival event (from Emitter.emit)."""
    global _quiet_until
    names = EVENT_SOUNDS.get(type_)
    if names:
        play(random.choice(names))
    for n in LAYERS.get(type_, ()):
        play(n)
    if type_ == "bomb_hit":
        _scheduled.append((_now() + BOMB_DELAY, "sfx_explosion"))
    if type_ == "game_over":
        _quiet_until = _now() + STING_GAP
        _set_music(None)


def countdown(prev, cd, total):
    """3-2-1: a beep each time the countdown crosses a third of its length (GO is game_start)."""
    step = total / 3
    for k in range(3):
        if prev <= k * step < cd:
            play("sfx_countdown_beep")


def _set_music(track):
    global _music_now
    if track == _music_now or not _ready():
        return
    _music_now = track
    try:
        if track is None or not _enabled:
            pygame.mixer.music.fadeout(MUSIC_FADE_MS)
            return
        pygame.mixer.music.load(os.path.join(ASSETS, MUSIC[track]))
        pygame.mixer.music.set_volume(MUSIC_VOLUME * _duck)
        pygame.mixer.music.play(loops=-1, fade_ms=MUSIC_FADE_MS)
    except (pygame.error, FileNotFoundError):
        pass


def update(app):
    """Once per frame: Sound On/Off, ducking under the rival's voice, music for the scene."""
    global _enabled, _duck, _music_now
    if not _ready():
        return
    enabled = bool(app.settings.get("sound", True))
    if enabled != _enabled:
        _enabled = enabled
        _music_now = "off"                    # force _set_music to act below
        if not enabled:
            pygame.mixer.music.stop()
            for i in range(pygame.mixer.get_num_channels()):
                if i != shared.VOICE_CHANNEL:
                    pygame.mixer.Channel(i).stop()
    _duck = shared.DUCK_LEVEL if shared.rival_speaking.is_set() else 1.0
    try:
        pygame.mixer.music.set_volume(MUSIC_VOLUME * _duck if _enabled else 0.0)
    except pygame.error:
        pass
    for item in [s for s in _scheduled if s[0] <= _now()]:
        _scheduled.remove(item)
        play(item[1])
    if _now() < _quiet_until:
        return
    playing = type(app.scene).__name__ == "PlayScene" and not getattr(app.scene, "ended", False)
    _set_music(("play" if playing else "menu") if _enabled else None)
