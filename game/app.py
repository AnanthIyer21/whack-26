"""The window, the 60 fps loop and switching between screens ("scenes").

How pygame works, in one paragraph: every frame we (1) read input events from the OS,
(2) update the game by dt seconds, (3) draw everything onto the screen surface, then
(4) flip() to show it. shared.FramePacer then waits until the next frame is due: a steady
60 fps that, unlike clock.tick_busy_loop, doesn't hog Python's lock and starve the vision
and rival threads (plain clock.tick oversleeps on macOS, ~39 fps).
"""
import queue
import time

import pygame

import shared
from . import config as C
from .background import CameraBackground
from .events import Emitter
from .input import HandInput, MouseInput, Viewport
from . import sfx


class App:
    def __init__(self, links, fullscreen=False, input_mode="mouse"):
        self.links = links
        # Team audio contract: mixer settings before init, channel 0 reserved for the rival.
        pygame.mixer.pre_init(shared.MIXER_FREQ, shared.MIXER_SIZE, shared.MIXER_CHANNELS, shared.MIXER_BUFFER)
        pygame.init()
        try:
            pygame.mixer.set_reserved(1)
        except pygame.error:
            pass                                       # no audio device: play silently
        pygame.display.set_caption("WHACK 26 - Fruit Ninja vs the Rival")
        # SCALED: we always draw at 1280x720 and pygame scales it to the window/fullscreen,
        # and maps mouse positions back to 1280x720 for us.
        try:
            self.screen = pygame.display.set_mode((C.W, C.H), pygame.SCALED, vsync=1)
        except pygame.error:
            self.screen = pygame.display.set_mode((C.W, C.H), pygame.SCALED)
        self.fullscreen = False
        if fullscreen:
            self.toggle_fullscreen()
        self.pacer = shared.FramePacer(shared.FPS)
        self.glow = pygame.Surface((C.W, C.H), pygame.SRCALPHA).convert_alpha()  # translucent effects layer
        self.fonts = {}
        self._text_cache = {}
        self.debug = False
        self.running = True

        self.events = Emitter(links.post_event)       # game -> rival, never blocks
        self.settings = {"seconds": links.default_seconds, "sound": True}
        self.viewport = Viewport()
        self.background = CameraBackground(links.get_latest_frame, self.viewport)
        self.inputs = {"mouse": MouseInput(), "hand": HandInput(links.get_hand_state, self.viewport)}
        self.input_name = input_mode if input_mode in self.inputs else "mouse"
        self.mouse_publishes = input_mode == "mouse"   # vision isn't running: we publish HandState

        # rival -> game: newest line (for the bubble) and the final roast (for game over)
        self.rival_line = None
        self.rival_line_at = 0.0
        self.final_line = None

        from .scenes.title import TitleScene
        self.scene = TitleScene(self)

    # ---- helpers used by scenes ---------------------------------------------------------
    @property
    def input(self):
        return self.inputs[self.input_name]

    def toggle_fullscreen(self):
        pygame.display.toggle_fullscreen()
        self.fullscreen = not self.fullscreen

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)   # SysFont hangs on macOS
        return self.fonts[size]

    def render(self, s, size, color):
        """Rendered text, cached (the HUD draws the same strings every frame)."""
        key = (s, size, color)
        img = self._text_cache.get(key)
        if img is None:
            if len(self._text_cache) > 400:
                self._text_cache.clear()
            img = self._text_cache[key] = self.font(size).render(s, True, color).convert_alpha()
        return img

    def text(self, surf, s, size, pos, color=(255, 255, 255), anchor="topleft", shadow=False):
        img = self.render(s, size, color)
        img.set_alpha(255)
        r = img.get_rect(**{anchor: pos})
        if shadow:
            sh = self.render(s, size, (0, 0, 0))
            sh.set_alpha(140)
            surf.blit(sh, r.move(2, 3))
        surf.blit(img, r)
        return r

    def switch_scene(self, scene):
        self.scene = scene

    def quit(self):
        self.running = False

    # ---- main loop ---------------------------------------------------------------------
    def run(self):
        last = time.monotonic()
        stop = self.links.stop_event
        while self.running and not stop.is_set():
            now = time.monotonic()
            dt = min(now - last, C.MAX_DT)
            last = now

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_f:
                    self.toggle_fullscreen()
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_d:
                    self.debug = not self.debug
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_TAB:
                    self.input_name = "hand" if self.input_name == "mouse" else "mouse"
                    if hasattr(self.input, "reset"):
                        self.input.reset()
                    self.scene.on_input_switched()
                else:
                    self.input.handle_event(ev)
                    self.scene.handle_event(ev)

            self._read_rival(now)
            self.scene.update(dt, now)
            sfx.update(self)              # music per scene, ducking, Sound On/Off (RBadiadka7)
            self.glow.fill((0, 0, 0, 0))
            self.scene.draw(self.screen, now)
            self._draw_corner_tags()
            pygame.display.flip()
            self.pacer.tick()
        # No pygame.quit() here: main.py quits pygame after the other threads have stopped
        # (the rival still needs the mixer to stop its voice channel).

    def poll_input(self, now):
        """Scenes call this once per frame. In mouse mode we also publish the HandState."""
        s = self.input.poll(now)
        if self.mouse_publishes and self.input_name == "mouse":
            self.links.set_hand_state(shared.HandState(
                sword_visible=True, sword_active=bool(s.gripping),
                blade_base=(s.base[0] / C.W, s.base[1] / C.H), blade_angle=float(s.angle),
                hands_in_frame=int(s.hands), gesture="none", confidence=1.0, t=now))
        return s

    def _read_rival(self, now):
        while True:
            try:
                line = self.links.rival_lines.get_nowait()
            except queue.Empty:
                break
            self.rival_line, self.rival_line_at = line, now
            if line.get("final"):
                self.final_line = line

    def _draw_corner_tags(self):
        self.text(self.screen, self.input.name, 20, (C.W - 8, C.H - 6), (200, 200, 200), "bottomright")
        if self.debug:
            lines = [f"fps {self.pacer.fps():5.1f}"] + self.scene.debug_lines()
            for i, s in enumerate(lines):
                self.text(self.screen, s, 22, (8, C.H - 8 - 20 * (len(lines) - i)), (255, 255, 0))
