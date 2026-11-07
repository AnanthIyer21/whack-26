"""The window, the 60 fps loop and switching between screens ("scenes").

How pygame works, in one paragraph: every frame we (1) read input events from the OS,
(2) update the game by dt seconds, (3) draw everything onto the screen surface, then
(4) flip() to show it. clock.tick(60) sleeps just enough to hold 60 frames per second.
"""
import time

import pygame

from . import config as C
from .input import MouseInput, HandInput, Viewport


class App:
    def __init__(self, links, fullscreen=False, input_mode="mouse"):
        self.links = links
        pygame.init()
        pygame.display.set_caption("WHACK 26 - Fruit Ninja vs the Rival")
        # SCALED: we always draw at 1280x720 and pygame scales it to the window/fullscreen,
        # and maps mouse positions back to 1280x720 for us.
        self.screen = pygame.display.set_mode((C.W, C.H), pygame.SCALED, vsync=1)
        if fullscreen:
            pygame.display.toggle_fullscreen()
        self.clock = pygame.time.Clock()
        self.glow = pygame.Surface((C.W, C.H), pygame.SRCALPHA).convert_alpha()  # translucent effects layer
        self.fonts = {}
        self._text_cache = {}
        self.debug = False
        self.running = True

        from .events import Emitter
        self.events = Emitter(links.events)          # game -> rival, never blocks
        self.settings = {"seconds": links.default_seconds}
        self.viewport = Viewport()
        self.inputs = {"mouse": MouseInput(links.blade_length * C.H), "hand": HandInput(links.get_hand_state, self.viewport)}
        self.input_name = input_mode if input_mode in self.inputs else "mouse"

        from .scenes.play import PlayScene
        self.scene = PlayScene(self)

    # ---- helpers used by scenes ---------------------------------------------------------
    @property
    def input(self):
        return self.inputs[self.input_name]

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
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

    def text(self, surf, s, size, pos, color=(255, 255, 255), anchor="topleft"):
        img = self.render(s, size, color)
        img.set_alpha(255)
        r = img.get_rect(**{anchor: pos})
        surf.blit(img, r)
        return r

    def switch_scene(self, scene):
        self.scene = scene

    # ---- main loop ---------------------------------------------------------------------
    def run(self):
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = min(now - last, C.MAX_DT)
            last = now

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_d:
                    self.debug = not self.debug
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_TAB:
                    self.input_name = "hand" if self.input_name == "mouse" else "mouse"
                    self.scene.on_input_switched()
                else:
                    self.input.handle_event(ev)
                    self.scene.handle_event(ev)

            self.scene.update(dt, now)
            self.glow.fill((0, 0, 0, 0))
            self.scene.draw(self.screen, now)
            self._draw_corner_tags()
            pygame.display.flip()
            self.clock.tick(C.FPS)
        pygame.quit()

    def _draw_corner_tags(self):
        self.text(self.screen, self.input.name, 20, (C.W - 8, C.H - 6), (200, 200, 200), "bottomright")
        if self.debug:
            lines = [f"fps {self.clock.get_fps():5.1f}"] + self.scene.debug_lines()
            for i, s in enumerate(lines):
                self.text(self.screen, s, 22, (8, C.H - 8 - 20 * (len(lines) - i)), (255, 255, 0))
