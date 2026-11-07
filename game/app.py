"""Window, main loop and switching between scenes."""
import pygame

from game import config


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
        }
        self.background = self._make_background()

        from game.scenes import TitleScene
        self.scene = TitleScene(self)

    def _make_background(self):
        """A vertical dark-wood gradient, drawn once."""
        bg = pygame.Surface((config.WIDTH, config.HEIGHT))
        for y in range(config.HEIGHT):
            k = y / config.HEIGHT
            c = [int(a + (b - a) * k) for a, b in zip(config.BG_TOP, config.BG_BOTTOM)]
            pygame.draw.line(bg, c, (0, y), (config.WIDTH, y))
        return bg

    def switch(self, scene):
        self.scene = scene

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
                else:
                    self.scene.handle(event)
            self.scene.update(dt)
            self.screen.blit(self.background, (0, 0))
            self.scene.draw(self.screen)
            if self.debug:
                self._draw_debug()
            pygame.display.flip()
        pygame.quit()

    def _draw_debug(self):
        from game import bridge
        text = f"FPS {self.clock.get_fps():4.0f}  input={self.input_mode}  src={bridge.SOURCE}  hand={self.sword_hand}"
        img = self.fonts["small"].render(text, True, config.WHITE)
        self.screen.blit(img, (10, config.HEIGHT - 28))
