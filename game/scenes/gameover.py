"""Game over: score, best combo, NEW BEST, and the rival's final roast.

The roast is the rival line marked "final": True. Until it arrives the bubble shows "...";
after 6 s with nothing we show a canned roast so the screen never hangs. Play again / Title
are clickable straight away; a fist held for 0.7 s (after opening your hand once) also replays.
"""
import math
import random

import pygame

from .. import config as C
from ..rival_ui import RivalDisplay
from ..ui import Button, FistHold, fist_ring

ROAST_TIMEOUT = 6.0
FALLBACK_ROASTS = (
    "I've seen sharper swordplay from a spoon.",
    "That fruit salad was mostly survivors.",
    "Remarkable. You made the fruit look skilled.",
    "My circuits recorded that. For training. On what not to do.",
)
TITLES = {"timer": "TIME'S UP", "lives": "OUT OF LIVES", "quit": "RUN ENDED"}


class GameOverScene:
    def __init__(self, app, snapshot, result):
        self.app = app
        self.snapshot = snapshot
        self.r = result
        self.t = 0.0
        self.hold = FistHold(need_release=True)
        self.again_btn = Button("Play again", (C.W * 0.3 - 140, 600), (250, 64))
        self.title_btn = Button("Title", (C.W * 0.3 + 140, 600), (250, 64))
        self.rival = RivalDisplay(app, 220)
        self.roast = None
        self.fallback = random.choice(FALLBACK_ROASTS)
        self.dark = pygame.Surface((C.W, C.H)).convert()
        self.dark.fill((5, 5, 12))
        self.sample = None
        # Party mode / leaderboard (RBadiadka7): a party run is saved under the player's name and the
        # buttons move the party on; a solo run that makes the all-time top 10 may type a name.
        self.party = app.party
        self.entry = None
        if self.party is not None:
            self.player = self.party.current
            self.party.record(self.r["score"], self.r["best_combo"])
            self.again_btn.label = "Leaderboard" if self.party.round_done else "Next player"
            self.title_btn.label = "End party"
            self.title_btn.danger = True
        elif app.leaderboard.qualifies(self.r["score"]):
            from .party import NameBox
            self.entry = NameBox((C.W - 450, 600, 400, 54))

    @property
    def typing(self):
        return self.entry is not None

    def _save_entry(self):
        if self.entry is not None and self.entry.text.strip():
            from ..leaderboard import clean_name
            self.app.leaderboard.add_alltime(clean_name(self.entry.text, "Player"), self.r["score"],
                                             self.r["best_combo"])
            self.saved_name = clean_name(self.entry.text, "Player")
        self.entry = None

    def on_input_switched(self):
        pass

    def _over_button(self):
        return self.app.input_name == "mouse" and (self.again_btn.contains_mouse() or self.title_btn.contains_mouse())

    def handle_event(self, ev):
        if self.entry is not None and ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._save_entry()
            elif ev.key == pygame.K_ESCAPE:
                self.entry = None                         # skip: not saved
            else:
                self.entry.key(ev)
            return
        if self.again_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
            self._again()
        elif self.title_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            self._save_entry()
            if self.party is not None:
                from .party import LeaderboardScene
                self.app.switch_scene(LeaderboardScene(self.app, ended_early=not self.party.round_done))
                return
            from .title import TitleScene
            self.app.switch_scene(TitleScene(self.app, need_release=True))

    def _again(self):
        self._save_entry()
        if self.party is not None:
            from .party import after_party_turn
            after_party_turn(self.app)
            return
        from .play import PlayScene
        self.app.switch_scene(PlayScene(self.app))

    def update(self, dt, now):
        self.t += dt

        s = self.sample = self.app.poll_input(now)
        if self.t > 1.0 and self.hold.update(s.good, dt, self._over_button() or self.entry is not None):
            self._again()
            return
        elif not s.good:
            self.hold.released = True     # opened the hand: a new fist may now replay
        line = self.app.final_line
        if line is not None and self.roast is None:
            self.roast = line
            self.rival.show(line, now)
            self.rival.line = dict(line, duration=1e9)    # keep it on screen

    def draw(self, screen, now):
        app = self.app
        screen.blit(self.snapshot, (0, 0))
        self.dark.set_alpha(int(190 * min(1.0, self.t / 0.4)))
        screen.blit(self.dark, (0, 0))

        lx = int(C.W * 0.3)
        app.text(screen, TITLES.get(self.r["reason"], "GAME OVER"), 92, (lx, 90), (255, 255, 255), "midtop", shadow=True)
        shown = int(self.r["score"] * min(1.0, self.t / 0.9))
        app.text(screen, str(shown), 150, (lx, 190), (255, 220, 80), "midtop", shadow=True)
        app.text(screen, "points", 34, (lx, 315), (220, 220, 235), "midtop", shadow=True)
        app.text(screen, f"Best combo  {self.r['best_combo']}", 42, (lx, 375), (230, 230, 245), "midtop", shadow=True)
        if self.r["new_best"] and self.r["score"] > 0:
            pulse = 1 + 0.06 * math.sin(now * 8)
            img = app.render("NEW BEST!", int(64 * pulse), (255, 120, 90))
            screen.blit(img, img.get_rect(midtop=(lx, 440)))
        else:
            app.text(screen, f"Best  {max(self.r['best_before'], self.r['score'])}", 36, (lx, 450),
                     (190, 190, 205), "midtop", shadow=True)

        self.again_btn.draw(app, screen)
        self.title_btn.draw(app, screen)
        hint = "or hold a fist to play again"
        if self.party is not None:
            hint = "or hold a fist for the leaderboard" if self.party.round_done else "or hold a fist: next player"
            app.text(screen, self.player, 40, (lx, 40), (255, 120, 170), "midtop", shadow=True)
        app.text(screen, hint, 26, (lx, 650), (170, 170, 190), "midtop", shadow=True)
        if self.entry is not None:
            app.text(screen, "ALL-TIME TOP 10!  type your name", 30, (self.entry.rect.centerx, 566),
                     (255, 220, 80), "midtop", shadow=True)
            self.entry.draw(app, screen, True, now)
            app.text(screen, "Enter: save   Esc: skip", 24, (self.entry.rect.centerx, 662), (170, 170, 190),
                     "midtop", shadow=True)
        elif getattr(self, "saved_name", None):
            app.text(screen, f"Saved to the top 10 as {self.saved_name}", 30, (C.W - 250, 620), (255, 220, 80),
                     "midtop", shadow=True)

        avatar = (C.W - 190, 430)
        if self.roast is not None:
            self.rival.draw(screen, now, avatar, C.W - 310, max_w=400, size=220, text_size=36)
        elif self.t < ROAST_TIMEOUT:
            self.rival.draw(screen, now, avatar, C.W - 310, max_w=400, size=220, text_size=44, thinking=True)
        else:
            self.rival.mood = "gloating"
            self.rival.draw(screen, now, avatar, C.W - 310, max_w=400, size=220, text_size=36,
                            text_override=self.fallback)

        s = self.sample
        if s and s.good and self.hold.held > 0:
            fist_ring(screen, s.base, self.hold.progress, now)

    def debug_lines(self):
        return [f"roast {'yes' if self.roast else 'waiting'} t {self.t:.1f} hold {self.hold.held:.2f}"]
