"""The game's screens. Each scene has handle(event), update(dt) and draw(surface)."""
import random
import time

import pygame

from game import bridge, config
from game.fruit import Spawner
from game.input import make_input
from game.rules import Rules
from game.slicing import swept_hit
from game.sword import Sword


def draw_text(surface, font, text, colour, center):
    img = font.render(text, True, colour)
    surface.blit(img, img.get_rect(center=center))
    return img.get_rect(center=center)


def send(app, ev):
    """Stamp round_id and send one event to the rival (never blocks)."""
    ev = dict(ev)
    type_ = ev.pop("type")
    sent = bridge.send_event(type_, round_id=app.round_id, **ev)
    app.last_events = ([f"{sent['type']} {ev}"] + app.last_events)[:5]
    return sent


class TitleScene:
    """Pick the sword hand (L/R or click), then Space/Enter to start."""

    def __init__(self, app):
        self.app = app
        cx, cy = config.WIDTH // 2, config.HEIGHT // 2 + 60
        self.buttons = {
            "left": pygame.Rect(cx - 330, cy - 90, 260, 180),
            "right": pygame.Rect(cx + 70, cy - 90, 260, 180),
        }
        bridge.set_sword_hand(app.sword_hand)

    def choose(self, hand):
        if hand != self.app.sword_hand:
            self.app.sword_hand = hand
            bridge.set_sword_hand(hand)

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_l:
                self.choose("left")
            elif event.key == pygame.K_r:
                self.choose("right")
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.app.switch(CountdownScene(self.app))
            elif event.key == pygame.K_ESCAPE:
                self.app.running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for hand, rect in self.buttons.items():
                if rect.collidepoint(event.pos):
                    self.choose(hand)

    def update(self, dt):
        pass

    def draw(self, surface):
        f = self.app.fonts
        draw_text(surface, f["big"], "FRUIT NINJA", config.GOLD, (config.WIDTH // 2, 130))
        draw_text(surface, f["small"], "vs the smug AI rival", config.WHITE, (config.WIDTH // 2, 195))
        draw_text(surface, f["mid"], "Pick your sword hand", config.WHITE, (config.WIDTH // 2, 290))
        for hand, rect in self.buttons.items():
            chosen = hand == self.app.sword_hand
            pygame.draw.rect(surface, config.GOLD if chosen else config.GREY, rect, 0 if chosen else 4, border_radius=18)
            colour = config.DARK if chosen else config.WHITE
            draw_text(surface, f["mid"], hand.upper(), colour, rect.center)
            draw_text(surface, f["small"], f"press {hand[0].upper()}", colour, (rect.centerx, rect.bottom - 25))
        draw_text(surface, f["small"], "SPACE to start  -  F fullscreen  -  D debug  -  ESC quit",
                  config.WHITE, (config.WIDTH // 2, config.HEIGHT - 60))


class CountdownScene:
    """3, 2, 1, SLICE! then into play. resume_to=PlayScene to continue a paused round."""

    def __init__(self, app, resume_to=None):
        self.app, self.resume_to, self.t = app, resume_to, 0.0

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.switch(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        if self.t >= 4 * config.COUNTDOWN_STEP:
            if self.resume_to:
                self.app.switch(self.resume_to)
            else:
                self.app.switch(PlayScene(self.app))

    def draw(self, surface):
        step = int(self.t / config.COUNTDOWN_STEP)
        text = ["3", "2", "1", "SLICE!"][min(step, 3)]
        draw_text(surface, self.app.fonts["big"], text, config.GOLD, (config.WIDTH // 2, config.HEIGHT // 2))


class PlayScene:
    def __init__(self, app):
        self.app = app
        app.round_id += 1
        bridge.drain_rival_lines()          # old lines must not leak into this round
        self.rules = Rules()
        self.spawner = Spawner()
        self.sword = Sword()
        self.input = make_input(app.input_mode)
        self.fruits = []
        self.popups = []                    # [text, x, y, time_left]
        self.elapsed = 0.0                  # simulation time of this round
        self.state = "playing"              # playing -> bomb -> (game over)
        self.bomb_timer = 0.0
        self.ended = False
        send(app, {"type": "game_start"})

    # --- input ---
    def handle(self, event):
        self.input.handle(event) if hasattr(self.input, "handle") else None
        if event.type == pygame.KEYDOWN and self.app.debug:
            if event.key == pygame.K_MINUS:
                config.CUT_SPEED = max(100, config.CUT_SPEED - 100)
            elif event.key == pygame.K_EQUALS:
                config.CUT_SPEED += 100
            elif event.key == pygame.K_LEFTBRACKET:
                self.sword.length = max(40, self.sword.length - 10)
            elif event.key == pygame.K_RIGHTBRACKET:
                self.sword.length += 10

    # --- game logic ---
    def update(self, dt):
        if self.state == "bomb":
            self.bomb_timer += dt
            if self.bomb_timer >= config.BOMB_FREEZE + config.BOMB_EXPLODE:
                self.finish("bomb")
            return

        self.elapsed += dt
        now = self.elapsed
        sample = self.input.update(dt)
        for ev in self.sword.update(sample, time.monotonic()):
            send(self.app, ev)

        for f in self.spawner.update(dt, self.elapsed):
            self.fruits.append(f)
        for f in self.fruits:
            f.update(dt)

        sweep = self.sword.sweep()
        if sweep and self.sword.speed >= config.CUT_SPEED:
            for f in self.fruits:
                if f.alive and swept_hit(*sweep, self.sword.length, (f.x, f.y), f.r):
                    if f.is_bomb:
                        self.hit_bomb(f)
                        return
                    f.alive = False
                    for ev in self.rules.on_cut(f.kind, f.points, now):
                        self.on_rule_event(ev, f.x, f.y)

        for ev in self.rules.update(now):
            self.on_rule_event(ev, config.WIDTH / 2, config.HEIGHT / 3)

        for f in self.fruits:
            if f.alive and f.fell_off():
                f.alive = False
                if not f.is_bomb:
                    side = "left" if f.x < config.WIDTH / 2 else "right"
                    for ev in self.rules.on_drop(f.kind, side):
                        self.on_rule_event(ev, f.x, config.HEIGHT - 40)
        self.fruits = [f for f in self.fruits if f.alive]

        for p in self.popups:
            p[3] -= dt
            p[2] -= 40 * dt
        self.popups = [p for p in self.popups if p[3] > 0]

        if self.rules.over:
            self.finish("lives")

    def on_rule_event(self, ev, x, y):
        send(self.app, ev)
        if ev["type"] == "slice":
            pts = config.GOLDEN[3] if ev["fruit"] == "golden" else 1
            self.popups.append([f"+{pts}", x, y, 0.6])
        elif ev["type"] == "combo":
            self.popups.append([f"COMBO x{ev['n']}", x, y, 1.0])
        elif ev["type"] == "streak":
            self.popups.append([f"STREAK {ev['n']}!", x, y, 1.0])
        elif ev["type"] == "life_lost":
            self.popups.append(["-1 life", x, y, 0.8])

    def hit_bomb(self, bomb):
        """Lock the game at once: no more cuts, spawns or lost lives."""
        for ev in self.rules.settle():
            send(self.app, ev)
        self.state = "bomb"
        self.bomb_pos = (bomb.x, bomb.y)
        self.sword.reset_history()
        send(self.app, {"type": "bomb_hit"})

    def finish(self, reason):
        if self.ended:
            return
        self.ended = True
        for ev in self.rules.settle():
            send(self.app, ev)
        bridge.drain_rival_lines()          # anything queued now is a mid-game taunt, not the roast
        stats = {"score": self.rules.score, "best_combo": self.rules.best_combo,
                 "duration": round(self.elapsed, 1), "reason": reason}
        send(self.app, {"type": "game_over", "want_final_roast": True, **stats})
        self.app.switch(GameOverScene(self.app, stats))

    # --- drawing ---
    def draw(self, surface):
        for f in self.fruits:
            f.draw(surface)
        if self.state == "bomb":
            k = self.bomb_timer
            if k < config.BOMB_FREEZE:
                surface.fill((255, 255, 255))
            else:
                r = int(40 + 900 * (k - config.BOMB_FREEZE) / config.BOMB_EXPLODE)
                pygame.draw.circle(surface, (255, 140, 30), (int(self.bomb_pos[0]), int(self.bomb_pos[1])), r)
            return
        self.sword.draw(surface)
        f = self.app.fonts
        for text, x, y, _ in self.popups:
            draw_text(surface, f["mid"], text, config.GOLD, (x, y))
        surface.blit(f["mid"].render(str(self.rules.score), True, config.WHITE), (24, 18))
        for i in range(config.LIVES):
            colour = (220, 50, 60) if i < self.rules.lives else (70, 50, 50)
            pygame.draw.circle(surface, colour, (40 + i * 34, 90), 12)
        if self.rules.streak >= config.STREAK_STEP:
            surface.blit(f["small"].render(f"streak {self.rules.streak}", True, config.GOLD), (24, 112))
        if self.app.debug:
            dbg = (f"tip {self.sword.speed:5.0f} px/s  cut>={config.CUT_SPEED:.0f} (-/=)  "
                   f"blade {self.sword.length:.0f}px ([/])  t={self.elapsed:4.1f}")
            surface.blit(f["small"].render(dbg, True, config.WHITE), (10, config.HEIGHT - 56))
            for i, line in enumerate(self.app.last_events):
                surface.blit(f["small"].render(line[:80], True, config.GREY), (760, 18 + i * 24))


CANNED_ROASTS = [
    "That's it? My toaster slices better.",
    "I've seen fruit salad with more fight in it.",
    "Next time, try opening your eyes.",
]


class GameOverScene:
    """Score at once; the rival's final roast if it arrives within 6 s, else a canned one."""

    def __init__(self, app, stats):
        self.app, self.stats, self.t = app, stats, 0.0
        self.roast = None
        app.best = max(app.best, stats["score"])
        self.new_best = stats["score"] >= app.best and stats["score"] > 0

    def handle(self, event):
        if self.t < 0.8:          # grace period so a swing/click at the end doesn't skip this screen
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.app.switch(CountdownScene(self.app))
            elif event.key == pygame.K_t:
                self.app.switch(TitleScene(self.app))
            elif event.key == pygame.K_ESCAPE:
                self.app.running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.app.switch(CountdownScene(self.app))

    def update(self, dt):
        self.t += dt
        if self.roast is None:
            for line in bridge.drain_rival_lines():
                # only a line tagged as the final roast counts; a late mid-game taunt never does
                if line.get("kind") != "final_roast":
                    continue
                if line.get("round_id", self.app.round_id) != self.app.round_id:
                    continue
                self.roast = line.get("text", "")
                break
            if self.roast is None and self.t >= config.FINAL_ROAST_WAIT:
                self.roast = self.canned()

    def canned(self):
        if self.stats["reason"] == "bomb":
            return "You sliced a BOMB. On purpose? Bold."
        if self.stats["score"] < 10:
            return "Single digits. I'm almost embarrassed for you."
        return random.choice(CANNED_ROASTS)

    def draw(self, surface):
        f, cx = self.app.fonts, config.WIDTH // 2
        headline = "BOOM!" if self.stats["reason"] == "bomb" else "OUT OF LIVES"
        draw_text(surface, f["big"], headline, (230, 70, 50), (cx, 120))
        draw_text(surface, f["mid"], f"Score {self.stats['score']}", config.WHITE, (cx, 230))
        draw_text(surface, f["small"], f"best combo {self.stats['best_combo']}   -   {self.stats['duration']} s",
                  config.WHITE, (cx, 285))
        if self.new_best:
            draw_text(surface, f["small"], "NEW BEST!", config.GOLD, (cx, 320))
        if self.roast is None:
            dots = "." * (1 + int(self.t * 3) % 3)
            draw_text(surface, f["mid"], f"rival is thinking{dots}", config.GREY, (cx, 430))
        else:
            draw_text(surface, f["mid"], f"\"{self.roast}\"", config.GOLD, (cx, 430))
        draw_text(surface, f["small"], "SPACE / click to play again   -   T title   -   ESC quit",
                  config.WHITE, (cx, config.HEIGHT - 60))
