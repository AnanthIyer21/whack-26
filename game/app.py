"""Window, main loop, switching between scenes, and things every scene shares
(the rival on screen, the fist tracker for hand input, the fake hand for testing)."""
import time

import pygame

from game import bridge, config

FIST_HOLD = 0.5   # seconds a fist must be held to start / resume / play again


class App:
    def __init__(self, input_mode="mouse", fullscreen=False, debug=False):
        pygame.init()
        # SCALED: we always draw at 1280x720 and pygame scales it to the window/fullscreen.
        self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT), pygame.SCALED)
        pygame.display.set_caption(config.TITLE)
        if fullscreen:
            pygame.display.toggle_fullscreen()
        self.clock = pygame.time.Clock()
        self.input_mode = input_mode
        self.debug = debug
        self.sword_hand = "right"
        self.round_id = 0
        self.best = 0
        self.last_events = []     # shown in the debug overlay
        self.running = True
        self.fonts = {
            "big": pygame.font.Font(None, 110),
            "mid": pygame.font.Font(None, 56),
            "small": pygame.font.Font(None, 30),
            "bubble": pygame.font.Font(None, 34),
        }
        from game import art
        from game.rival_view import RivalView
        self.background = art.make_background()
        self.canvas = pygame.Surface((config.WIDTH, config.HEIGHT))   # scenes draw here; shake moves it
        self.rival = RivalView(self.fonts["bubble"])

        # fist tracker (hand input only): how long the sword hand has been gripping
        self.fist_time = 0.0
        self.fist_armed = False   # must see an open hand after each scene change before a fist counts

        # fake hand for testing hand input without Aaron's vision
        self.fake_vision = None
        if bridge.SOURCE == "fakes":
            from game.fakes import FakeVision
            self.fake_vision = FakeVision(config.WIDTH, config.HEIGHT)

        from game.scenes import TitleScene
        self.scene = TitleScene(self)

    def switch(self, scene):
        self.scene = scene
        self.fist_time, self.fist_armed = 0.0, False

    def set_input_mode(self, mode):
        self.input_mode = mode
        print(f"[game] input = {mode}")

    def fist_ready(self):
        """True once a fist has been held FIST_HOLD seconds (after an open hand in this scene)."""
        return self.input_mode == "hand" and self.fist_armed and self.fist_time >= FIST_HOLD

    def _update_fist(self, dt):
        if self.input_mode != "hand":
            return
        hs = bridge.get_hand_state()
        gripping = bool(hs and hs.sword_visible and hs.sword_active and time.monotonic() - hs.t < 0.25)
        if gripping:
            self.fist_time += dt
        else:
            self.fist_time, self.fist_armed = 0.0, True

    def _route_rival_lines(self):
        for line in bridge.drain_rival_lines():
            if hasattr(self.scene, "offer") and self.scene.offer(line):
                continue   # the game-over screen took it as the final roast
            self.rival.say(line)

    def run(self):
        while self.running:
            dt = min(self.clock.tick(config.FPS) / 1000, config.MAX_DT)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                    self.debug = not self.debug
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_h and self.fake_vision:
                    self.fake_vision.toggle_visible()
                else:
                    self.scene.handle(event)
            if self.fake_vision and self.input_mode == "hand":
                self.fake_vision.feed(pygame.mouse.get_pos(), pygame.mouse.get_pressed()[0],
                                      pygame.key.get_pressed()[pygame.K_o])
            self._update_fist(dt)
            self._route_rival_lines()
            self.scene.update(dt)
            self.rival.update(dt)

            self.canvas.blit(self.background, (0, 0))
            self.scene.draw(self.canvas)
            self.rival.draw(self.canvas)
            if self.debug:
                self._draw_debug()
            ox, oy = self.scene.shake_offset() if hasattr(self.scene, "shake_offset") else (0, 0)
            if ox or oy:
                self.screen.fill((0, 0, 0))
            self.screen.blit(self.canvas, (int(ox), int(oy)))
            pygame.display.flip()
        pygame.quit()

    def _draw_debug(self):
        text = f"FPS {self.clock.get_fps():4.0f}  input={self.input_mode}  src={bridge.SOURCE}  hand={self.sword_hand}"
        if self.input_mode == "hand":
            hs = bridge.get_hand_state()
            if hs:
                text += (f"  age={1000 * (time.monotonic() - hs.t):3.0f}ms vis={int(hs.sword_visible)} "
                         f"grip={int(hs.sword_active)} pose={int(hs.pause_pose)} fist={self.fist_time:.1f}")
            if self.fake_vision:
                text += "  [fake: mouse=fist, H hide, O palms up]"
        img = self.fonts["small"].render(text, True, config.WHITE)
        self.canvas.blit(img, (10, config.HEIGHT - 28))
