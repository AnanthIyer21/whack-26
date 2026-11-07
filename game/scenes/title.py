"""Title screen: hold up one hand and make a fist (a ring fills over 0.7 s) to start."""
import math

import pygame

from .. import config as C
from ..blade import Blade
from ..rival_ui import RivalDisplay
from ..storage import load_best
from ..ui import Button, FistHold, fist_ring


class TitleScene:
    def __init__(self, app, need_release=False):
        self.app = app
        self.hold = FistHold(need_release)
        self.best = load_best()
        self.settings_btn = Button("Settings", (C.W // 2 - 150, 610), (260, 64))
        self.quit_btn = Button("Quit", (C.W // 2 + 150, 610), (260, 64))
        self.blade = Blade(app.links.blade_length)
        self.rival = RivalDisplay(app, 150)
        self.sample = None
        self.t = 0.0

    def on_input_switched(self):
        self.blade.reset_history()

    def _over_button(self):
        return self.app.input_name == "mouse" and (self.settings_btn.contains_mouse() or self.quit_btn.contains_mouse())

    def handle_event(self, ev):
        if self.settings_btn.clicked(ev):
            from .settings import SettingsScene
            self.app.switch_scene(SettingsScene(self.app))
        elif self.quit_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            self.app.quit()
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
            self._start()

    def _start(self):
        from .play import PlayScene
        self.app.switch_scene(PlayScene(self.app))

    def update(self, dt, now):
        self.t += dt
        s = self.sample = self.app.poll_input(now)
        blocked = self._over_button()
        if self.hold.update(s.good, dt, blocked):
            self._start()
            return
        b = self.blade
        if s.good and not blocked:
            if b.state == "sheathed":
                b.draw_out(now)
            elif b.state == "frozen":
                b.unfreeze()
            b.update(s, now)
        elif b.state != "sheathed":
            b.sheathe()
        b.take_sweeps()
        self.rival.sync(now)

    def draw(self, screen, now):
        app = self.app
        app.background.draw(screen)
        cx = C.W // 2
        wob = math.sin(self.t * 2) * 4
        app.text(screen, C.TITLE, 110, (cx, 120 + wob), (255, 255, 255), "midtop", shadow=True)
        app.text(screen, C.SUBTITLE, 40, (cx, 235), (255, 210, 90), "midtop", shadow=True)
        pulse = int(200 + 55 * math.sin(self.t * 4))
        app.text(screen, "Hold up one hand and make a fist", 56, (cx, 360), (pulse, pulse, 255), "midtop", shadow=True)
        hint = "(mouse: hold the left button)" if app.input_name == "mouse" else "one hand only - the sword appears in your fist"
        app.text(screen, hint, 30, (cx, 418), (200, 200, 215), "midtop", shadow=True)
        if self.best:
            app.text(screen, f"Best  {self.best}", 34, (cx, 480), (255, 220, 80), "midtop", shadow=True)

        self.settings_btn.draw(app, screen)
        self.quit_btn.draw(app, screen)
        self.rival.draw(screen, now, (C.W - 100, 100), C.W - 190)

        self.blade.draw(screen, app.glow, now)
        screen.blit(app.glow, (0, 0))
        s = self.sample
        if s and s.good and self.hold.held > 0:
            fist_ring(screen, s.base, self.hold.progress, now)

    def debug_lines(self):
        s = self.sample
        return [f"hold {self.hold.held:.2f}  released {self.hold.released}"] + (
            [f"hands {s.hands} grip {s.gripping} stale {s.stale} good {s.good}"] if s else [])
