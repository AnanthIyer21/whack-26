"""Party mode (RBadiadka7): set up players, take turns, then a leaderboard with GRIP-9000's roast.

Title -> PartySetupScene (how many players + names) -> NextUpScene ("Next up: Ananth") -> PlayScene
-> GameOverScene ("Next player") -> NextUpScene ... -> LeaderboardScene (party board + all-time top 10)
-> "Another round" (same players, best score counts) or "End party" (party board wiped).
Scenes with `typing = True` get every key (the app's F / D / Tab shortcuts are off while typing).
"""
import math

import pygame

import shared
from .. import config as C
from ..leaderboard import MAX_PLAYERS, MIN_PLAYERS, NAME_MAX, Party
from ..rival_ui import RivalDisplay
from ..ui import Button, FistHold, fist_ring

GOLD, WHITE, DIM, PINK = (255, 220, 80), (255, 255, 255), (170, 170, 190), (255, 120, 170)
ROAST_TIMEOUT = 6.0


class NameBox:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.text = ""

    def key(self, ev):
        """Returns True if the key was used for typing."""
        if ev.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
            return True
        ch = ev.unicode
        if ch and ch.isprintable() and len(self.text) < NAME_MAX:
            self.text += ch
            return True
        return False

    def draw(self, app, screen, focused, now, label="", placeholder=""):
        edge = GOLD if focused else (150, 160, 210)
        pygame.draw.rect(screen, (0, 0, 0), self.rect.move(0, 4), border_radius=12)
        pygame.draw.rect(screen, (30, 32, 52), self.rect, border_radius=12)
        pygame.draw.rect(screen, edge, self.rect, 3, border_radius=12)
        if label:
            app.text(screen, label, 30, (self.rect.x - 14, self.rect.centery), DIM, "midright")
        x = self.rect.x + 16
        if self.text:
            r = app.text(screen, self.text, 38, (x, self.rect.centery), WHITE, "midleft")
            x = r.right + 3
        elif placeholder and not focused:
            app.text(screen, placeholder, 34, (x, self.rect.centery), (110, 110, 130), "midleft")
        if focused and int(now * 2) % 2 == 0:
            pygame.draw.rect(screen, GOLD, (x, self.rect.centery - 15, 3, 30))


class PartySetupScene:
    typing = True

    def __init__(self, app):
        self.app = app
        last = app.leaderboard.last_names()
        self.count = max(MIN_PLAYERS, min(MAX_PLAYERS, len(last) or 4))
        self.boxes = []
        for i in range(MAX_PLAYERS):
            col, row = i // 4, i % 4
            box = NameBox((C.W // 2 - 470 + col * 560, 250 + row * 72, 380, 54))
            box.text = last[i] if i < len(last) else ""
            self.boxes.append(box)
        self.focus = 0
        cx = C.W // 2
        self.minus = Button("-", (cx - 110, 175), (70, 60))
        self.plus = Button("+", (cx + 110, 175), (70, 60))
        self.start_btn = Button("Start", (cx + 150, 645), (260, 64), selected=True)
        self.back_btn = Button("Back", (cx - 150, 645), (260, 64))

    def on_input_switched(self):
        pass

    def _start(self):
        names = [b.text for b in self.boxes[:self.count]]
        self.app.party = Party(names, self.app.leaderboard)
        self.app.switch_scene(NextUpScene(self.app))

    def _back(self):
        from .title import TitleScene
        self.app.switch_scene(TitleScene(self.app))

    def handle_event(self, ev):
        if self.minus.clicked(ev):
            self.count = max(MIN_PLAYERS, self.count - 1)
            self.focus = min(self.focus, self.count - 1)
        elif self.plus.clicked(ev):
            self.count = min(MAX_PLAYERS, self.count + 1)
        elif self.start_btn.clicked(ev):
            self._start()
        elif self.back_btn.clicked(ev):
            self._back()
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, b in enumerate(self.boxes[:self.count]):
                if b.rect.collidepoint(ev.pos):
                    self.focus = i
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self._back()
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.focus >= self.count - 1:
                    self._start()
                else:
                    self.focus += 1
            elif ev.key == pygame.K_TAB:
                step = -1 if ev.mod & pygame.KMOD_SHIFT else 1
                self.focus = (self.focus + step) % self.count
            elif ev.key == pygame.K_UP:
                self.focus = (self.focus - 1) % self.count
            elif ev.key == pygame.K_DOWN:
                self.focus = (self.focus + 1) % self.count
            else:
                self.boxes[self.focus].key(ev)

    def update(self, dt, now):
        self.app.poll_input(now)

    def draw(self, screen, now):
        app = self.app
        app.background.draw(screen)
        cx = C.W // 2
        app.text(screen, "PARTY", 90, (cx, 30), WHITE, "midtop", shadow=True)
        app.text(screen, "Players", 34, (cx - 330, 175), DIM, "midleft", shadow=True)
        app.text(screen, str(self.count), 70, (cx, 175), GOLD, "center", shadow=True)
        self.minus.draw(app, screen)
        self.plus.draw(app, screen)
        for i, b in enumerate(self.boxes[:self.count]):
            b.draw(app, screen, i == self.focus, now, label=f"{i + 1}.", placeholder=f"Player {i + 1}")
        app.text(screen, "type names  -  Enter: next / start  -  Esc: back", 26, (cx, 588), DIM, "midtop",
                 shadow=True)
        self.back_btn.draw(app, screen)
        self.start_btn.draw(app, screen)

    def debug_lines(self):
        return [f"party setup {self.count} players, focus {self.focus}"]


class NextUpScene:
    """'Next up: NAME' - the player makes a fist (or clicks Start / presses Space) to begin their turn."""

    def __init__(self, app):
        self.app = app
        self.hold = FistHold(need_release=True)
        cx = C.W // 2
        self.start_btn = Button("Start", (cx - 150, 620), (260, 64), selected=True)
        self.end_btn = Button("End party", (cx + 150, 620), (260, 64), danger=True)
        self.rival = RivalDisplay(app, 150)
        self.sample = None
        self.t = 0.0

    def on_input_switched(self):
        pass

    def _over_button(self):
        return self.app.input_name == "mouse" and (self.start_btn.contains_mouse() or self.end_btn.contains_mouse())

    def _go(self):
        from .play import PlayScene
        self.app.switch_scene(PlayScene(self.app))

    def handle_event(self, ev):
        if self.start_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
            self._go()
        elif self.end_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            self.app.switch_scene(LeaderboardScene(self.app, ended_early=True))

    def update(self, dt, now):
        self.t += dt
        s = self.sample = self.app.poll_input(now)
        if self.hold.update(s.good, dt, self._over_button()):
            self._go()
            return
        self.rival.sync(now)

    def draw(self, screen, now):
        app, party = self.app, self.app.party
        app.background.draw(screen)
        cx = C.W // 2
        app.text(screen, f"ROUND {party.round}  -  PLAYER {party.turn + 1} OF {len(party.names)}", 36, (cx, 90),
                 DIM, "midtop", shadow=True)
        app.text(screen, "NEXT UP", 70, (cx, 160), WHITE, "midtop", shadow=True)
        pulse = 1 + 0.04 * math.sin(self.t * 5)
        img = app.render(party.current, int(120 * pulse), GOLD)
        screen.blit(img, img.get_rect(center=(cx, 330)))
        hint = "hold the left button to start" if app.input_name == "mouse" else "make a fist to start"
        app.text(screen, hint, 44, (cx, 440), (200, 200, 255), "midtop", shadow=True)
        later = party.names[party.turn + 1:]
        if later:
            app.text(screen, "then: " + ", ".join(later), 28, (cx, 505), DIM, "midtop", shadow=True)
        self.start_btn.draw(app, screen)
        self.end_btn.draw(app, screen)
        self.rival.draw(screen, now, (C.W - 100, 100), C.W - 190)
        s = self.sample
        if s and s.good and self.hold.held > 0:
            fist_ring(screen, s.base, self.hold.progress, now)

    def debug_lines(self):
        return [f"next up {self.app.party.current} hold {self.hold.held:.2f}"]


def after_party_turn(app):
    """Where to go after a party player's game over screen."""
    if app.party.round_done:
        app.switch_scene(LeaderboardScene(app))
    else:
        app.switch_scene(NextUpScene(app))


class LeaderboardScene:
    def __init__(self, app, ended_early=False):
        self.app = app
        self.t = 0.0
        self.ended_early = ended_early
        self.rows = app.party.standings()
        self.top = app.leaderboard.top()
        cx = C.W // 2
        self.again_btn = Button("Another round", (cx - 170, 660), (300, 64), selected=True)
        self.end_btn = Button("End party", (cx + 170, 660), (300, 64), danger=True)
        self.rival = RivalDisplay(app, 180)
        self.roast = None
        played = [(n, s) for _, n, s in self.rows if s is not None]
        # GRIP-9000 roasts the final standings by name (needs shared.ev_party_over; skipped until it exists)
        self.asked = False
        app.final_line = None
        if played and hasattr(shared, "ev_party_over"):
            app.events.emit("party_over", standings=[{"name": n, "score": s} for n, s in played])
            self.asked = True

    def on_input_switched(self):
        pass

    def handle_event(self, ev):
        if self.again_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
            self.app.party.next_round()
            self.app.switch_scene(NextUpScene(self.app))
        elif self.end_btn.clicked(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            self.app.party.end()
            self.app.party = None
            from .title import TitleScene
            self.app.switch_scene(TitleScene(self.app, need_release=True))

    def update(self, dt, now):
        self.t += dt
        self.app.poll_input(now)
        line = self.app.final_line
        if line is not None and self.roast is None:
            self.roast = line
            self.rival.show(line, now)
            self.rival.line = dict(line, duration=1e9)
        if self.roast is None:
            self.rival.sync(now)

    def draw(self, screen, now):
        app = self.app
        app.background.draw(screen)
        title = "PARTY LEADERBOARD" + (f"  -  ROUND {app.party.round}" if app.party.round > 1 else "")
        app.text(screen, title, 64, (60, 28), WHITE, "topleft", shadow=True)
        if self.ended_early:
            app.text(screen, "party ended early", 28, (64, 92), DIM, "topleft", shadow=True)
        # party board (left)
        y = 130
        for i, (rank, name, score) in enumerate(self.rows):
            shown_at = 0.25 + 0.18 * (len(self.rows) - 1 - i)     # reveal from last place up
            if self.t < shown_at:
                continue
            col = GOLD if rank == 1 and score is not None else WHITE
            size = 52 if rank == 1 else 42
            app.text(screen, f"{rank}.", size, (70, y), col, "topleft", shadow=True)
            app.text(screen, name, size, (130, y), col, "topleft", shadow=True)
            app.text(screen, "-" if score is None else str(score), size, (620, y), col, "topright", shadow=True)
            y += 58 if rank == 1 else 52
        # all-time top 10 (right)
        x = 700
        app.text(screen, "ALL-TIME TOP 10", 36, (x, 132), PINK, "topleft", shadow=True)
        for i, (name, score) in enumerate(self.top):
            yy = 176 + i * 34
            app.text(screen, f"{i + 1}. {name}", 30, (x, yy), WHITE, "topleft", shadow=True)
            app.text(screen, str(score), 30, (x + 300, yy), GOLD, "topright", shadow=True)
        if not self.top:
            app.text(screen, "no scores yet", 30, (x, 176), DIM, "topleft", shadow=True)

        avatar = (C.W - 100, 556)
        if self.roast is not None:
            self.rival.draw(screen, now, avatar, C.W - 180, max_w=400, size=160, text_size=32)
        elif self.asked and self.t < ROAST_TIMEOUT:
            self.rival.draw(screen, now, avatar, C.W - 180, max_w=400, size=160, text_size=40, thinking=True)
        else:
            self.rival.draw(screen, now, avatar, C.W - 180, max_w=400, size=160)
        self.again_btn.draw(app, screen)
        self.end_btn.draw(app, screen)

    def debug_lines(self):
        return [f"leaderboard rows {len(self.rows)} roast {'yes' if self.roast else 'no'}"]
