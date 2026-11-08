"""Settings: game length (30/60/90/120 s, default 60), fullscreen, sound. Mouse buttons."""
import pygame

from .. import config as C
from ..ui import Button

LENGTHS = (30, 60, 90, 120)


class SettingsScene:
    def __init__(self, app):
        self.app = app
        cx = C.W // 2
        self.length_btns = [Button(f"{n} s", (cx - 330 + i * 220, 270), (190, 64)) for i, n in enumerate(LENGTHS)]
        self.full_btn = Button("", (cx - 160, 420), (290, 64))
        self.sound_btn = Button("", (cx + 160, 420), (290, 64))
        self.back_btn = Button("Back", (cx, 600), (260, 64))

    def on_input_switched(self):
        pass

    def handle_event(self, ev):
        app = self.app
        for n, b in zip(LENGTHS, self.length_btns):
            if b.clicked(ev):
                app.settings["seconds"] = n
        if self.full_btn.clicked(ev):
            app.toggle_fullscreen()
        if self.sound_btn.clicked(ev):
            app.settings["sound"] = not app.settings["sound"]
        if self.back_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            from .title import TitleScene
            app.switch_scene(TitleScene(app))

    def update(self, dt, now):
        self.app.poll_input(now)

    def draw(self, screen, now):
        app = self.app
        app.background.draw(screen)
        cx = C.W // 2
        app.text(screen, "Settings", 90, (cx, 60), (255, 255, 255), "midtop", shadow=True)
        app.text(screen, "Game length", 40, (cx, 190), (220, 220, 235), "midtop", shadow=True)
        for n, b in zip(LENGTHS, self.length_btns):
            b.selected = app.settings["seconds"] == n
            b.draw(app, screen)
        self.full_btn.label = "Fullscreen: " + ("On" if app.fullscreen else "Off")
        self.sound_btn.label = "Sound: " + ("On" if app.settings["sound"] else "Off")
        self.full_btn.draw(app, screen)
        self.sound_btn.draw(app, screen)
        app.text(screen, "F also toggles fullscreen", 26, (cx, 470), (170, 170, 190), "midtop", shadow=True)
        self.back_btn.draw(app, screen)

    def debug_lines(self):
        return [str(self.app.settings)]
