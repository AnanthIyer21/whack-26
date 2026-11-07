"""The game's screens. Each scene has handle(event), update(dt) and draw(surface)."""
import math
import random
import time

import pygame

from game import art, bridge, config, sound
from game.effects import Particles, Popups, Shake, Splats
from game.fruit import Spawner, split
from game.input import HandInput, make_input
from game.rules import Rules
from game.slicing import swept_hit, tip
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
        if self.app.fist_ready():
            self.app.switch(CountdownScene(self.app))

    def draw(self, surface):
        f = self.app.fonts
        start = "SPACE or hold a fist to start" if self.app.input_mode == "hand" else "SPACE to start"
        draw_text(surface, f["small"], f"{start}   (input: {self.app.input_mode.upper()})", config.GOLD,
                  (config.WIDTH // 2, config.HEIGHT - 100))
        draw_text(surface, f["big"], "FRUIT NINJA", config.GOLD, (config.WIDTH // 2, 130))
        draw_text(surface, f["small"], "vs the smug AI rival", config.WHITE, (config.WIDTH // 2, 195))
        draw_text(surface, f["mid"], "Pick your sword hand", config.WHITE, (config.WIDTH // 2, 290))
        for hand, rect in self.buttons.items():
            chosen = hand == self.app.sword_hand
            pygame.draw.rect(surface, config.GOLD if chosen else config.GREY, rect, 0 if chosen else 4, border_radius=18)
            colour = config.DARK if chosen else config.WHITE
            draw_text(surface, f["mid"], hand.upper(), colour, rect.center)
            draw_text(surface, f["small"], f"press {hand[0].upper()}", colour, (rect.centerx, rect.bottom - 25))
        draw_text(surface, f["small"], "F fullscreen  -  M mute  -  D debug  -  ESC quit",
                  config.WHITE, (config.WIDTH // 2, config.HEIGHT - 60))


class CountdownScene:
    """3, 2, 1, SLICE! then into play. resume_to=PlayScene to continue a paused round."""

    def __init__(self, app, resume_to=None):
        self.app, self.resume_to, self.t = app, resume_to, 0.0

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and not self.resume_to:
            self.app.switch(TitleScene(self.app))

    def update(self, dt):
        before = int(self.t / config.COUNTDOWN_STEP)
        self.t += dt
        step = int(self.t / config.COUNTDOWN_STEP)
        if self.t == dt or step != before:
            if step < 3:
                sound.play("beep")
            elif step == 3:
                sound.play("go")
        if self.t >= 4 * config.COUNTDOWN_STEP:
            if self.resume_to:
                self.resume_to.resumed()
                self.app.switch(self.resume_to)
            else:
                self.app.switch(PlayScene(self.app))

    def draw(self, surface):
        if self.resume_to:
            self.resume_to.draw(surface)
            dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 110))
            surface.blit(dim, (0, 0))
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
        self.fruits, self.halves = [], []
        self.particles, self.splats = Particles(), Splats()
        self.popups = Popups(app.fonts["mid"])
        self.shake = Shake()
        self.elapsed = 0.0                  # simulation time of this round
        self.state = "playing"              # playing -> bomb -> (game over)
        self.bomb_timer = 0.0
        self.exploded = False
        self.ended = False
        self.pose_armed = False             # palms-up must be released before it can pause (again)
        self.was_fast, self.last_swoosh = False, -1.0
        app.rival.clear()
        send(app, {"type": "game_start"})

    # --- input ---
    def handle(self, event):
        if hasattr(self.input, "handle"):
            self.input.handle(event)
        if event.type == pygame.KEYDOWN and self.state == "playing":
            if event.key in (pygame.K_p, pygame.K_ESCAPE):
                self.pause("key")
                return
            if event.key == pygame.K_TAB:
                self.app.set_input_mode("hand" if self.app.input_mode == "mouse" else "mouse")
                self.input = make_input(self.app.input_mode)
                self.sword.reset_history()
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
        self.shake.update(dt)
        if self.state == "bomb":
            self.update_bomb(dt)
            return

        self.elapsed += dt
        now = self.elapsed
        sample = self.input.update(dt)
        for ev in self.sword.update(sample, time.monotonic(), dt):
            send(self.app, ev)
        if self.sword.just_drew:
            sound.play("draw")
        elif self.sword.just_sheathed:
            sound.play("sheathe")
        fast = self.sword.ready and self.sword.speed >= config.CUT_SPEED
        if fast and not self.was_fast and self.elapsed - self.last_swoosh > 0.15:
            sound.play("swoosh", random.uniform(0.7, 1.0))
            self.last_swoosh = self.elapsed
        self.was_fast = fast
        if isinstance(self.input, HandInput):
            if not self.input.pause_pose:
                self.pose_armed = True
            elif self.pose_armed:
                self.pause("pose")
                return
            if self.input.lost_for >= 1.0:
                self.pause("hand_lost")
                return

        for f in self.spawner.update(dt, self.elapsed):
            self.fruits.append(f)
        for f in self.fruits:
            f.update(dt)
        self.update_effects(dt)

        sweep = self.sword.sweep()
        if sweep and self.sword.speed >= config.CUT_SPEED:
            b0, a0, b1, a1 = sweep
            t0, t1 = tip(b0, a0, self.sword.length), tip(b1, a1, self.sword.length)
            cut_angle = math.atan2(t1[1] - t0[1], t1[0] - t0[0])
            for f in self.fruits:
                if f.alive and swept_hit(*sweep, self.sword.length, (f.x, f.y), f.r):
                    if f.is_bomb:
                        self.hit_bomb(f)
                        return
                    self.cut(f, cut_angle, now)

        for ev in self.rules.update(now):
            self.on_rule_event(ev, config.WIDTH / 2, config.HEIGHT / 3)

        for f in self.fruits:
            if f.alive and f.fell_off():
                f.alive = False
                if not f.is_bomb:
                    side = "left" if f.x < config.WIDTH / 2 else "right"
                    for ev in self.rules.on_drop(f.kind, side):
                        self.on_rule_event(ev, min(max(f.x, 80), config.WIDTH - 80), config.HEIGHT - 50)
        self.fruits = [f for f in self.fruits if f.alive]
        sound.set_fuse(any(f.is_bomb for f in self.fruits))

        if self.rules.over:
            self.finish("lives")

    def update_effects(self, dt):
        for h in self.halves:
            h.update(dt)
        self.halves = [h for h in self.halves if not h.gone()]
        self.particles.update(dt)
        self.splats.update(dt)
        self.popups.update(dt)

    def cut(self, f, cut_angle, now):
        f.alive = False
        sound.play("slice", random.uniform(0.8, 1.0))
        self.halves += split(f, cut_angle)
        juice = art.JUICE.get(f.kind, (240, 240, 200))
        self.particles.burst(f.x, f.y, juice, n=18, bias=cut_angle)
        self.splats.add(f.x, f.y, juice, f.r)
        if f.kind == "golden":
            self.particles.burst(f.x, f.y, (255, 240, 150), n=30, speed=(200, 600), size=(2, 4), gravity=200)
        for ev in self.rules.on_cut(f.kind, f.points, now):
            self.on_rule_event(ev, f.x, f.y)

    def on_rule_event(self, ev, x, y):
        send(self.app, ev)
        t = ev["type"]
        if t == "slice" and ev["fruit"] == "golden":
            self.popups.add(f"+{config.GOLDEN[3]}", x, y - 30, config.GOLD, 0.9)
        elif t == "combo":
            self.popups.add(f"COMBO x{ev['n']}!", x, y, (255, 120, 60), 1.1)
            sound.play("combo")
            self.shake.start(4 + ev["n"], 0.25)
        elif t == "streak":
            self.popups.add(f"STREAK {ev['n']}", x, y + 60, (120, 220, 255), 1.0)
            sound.play("streak")
        elif t == "life_lost":
            self.popups.add("X", x, y, (230, 50, 50), 0.8)
            sound.play("life_lost")

    def pause(self, reason):
        self.pose_armed = False
        sound.play("pause")
        send(self.app, {"type": "pause", "reason": reason})
        self.app.switch(PauseScene(self.app, self, reason))

    def resumed(self):
        """Called when the resume countdown ends: forget old blade positions."""
        self.sword.reset_history()
        self.sword.active = False
        self.sword.cur = None
        self.input = make_input(self.app.input_mode)

    def hit_bomb(self, bomb):
        """Lock the game at once: no more cuts, spawns or lost lives."""
        for ev in self.rules.settle():
            send(self.app, ev)
        self.state = "bomb"
        sound.set_fuse(False)
        self.bomb_pos = (bomb.x, bomb.y)
        bomb.alive = False
        self.sword.reset_history()
        send(self.app, {"type": "bomb_hit"})

    def update_bomb(self, dt):
        self.bomb_timer += dt
        if self.bomb_timer < config.BOMB_FREEZE:
            return                                   # hit-stop: the world is frozen
        if not self.exploded:
            self.exploded = True
            sound.play("boom")
            bx, by = self.bomb_pos
            self.shake.start(18, 0.8)
            self.particles.burst(bx, by, (255, 200, 60), n=60, speed=(300, 900), size=(4, 9), life=(0.5, 1.1), gravity=300)
            self.particles.burst(bx, by, (255, 90, 20), n=50, speed=(200, 700), size=(5, 11), life=(0.6, 1.2), gravity=200)
            self.particles.burst(bx, by, (70, 65, 60), n=40, speed=(100, 400), size=(6, 14), life=(0.8, 1.4), gravity=-50)
            for f in self.fruits:                     # blast everything away
                a = math.atan2(f.y - by, f.x - bx)
                f.vx += math.cos(a) * 900
                f.vy += math.sin(a) * 900 - 300
        for f in self.fruits:
            f.update(dt)
        self.update_effects(dt)
        if self.bomb_timer >= config.BOMB_FREEZE + config.BOMB_EXPLODE:
            self.finish("bomb")

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
        sound.play("game_over")
        self.app.switch(GameOverScene(self.app, stats))

    def shake_offset(self):
        return self.shake.offset()

    # --- drawing ---
    def draw(self, surface):
        self.splats.draw(surface)
        for h in self.halves:
            h.draw(surface)
        for f in self.fruits:
            f.draw(surface, self.elapsed)
        self.particles.draw(surface)
        if self.state == "bomb":
            self.draw_bomb(surface)
        else:
            self.sword.draw(surface)
        self.popups.draw(surface)
        self.draw_hud(surface)

    def draw_bomb(self, surface):
        k = self.bomb_timer
        bx, by = int(self.bomb_pos[0]), int(self.bomb_pos[1])
        if k < config.BOMB_FREEZE:
            flash = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(230 * (1 - k / config.BOMB_FREEZE) ** 0.5)))
            surface.blit(flash, (0, 0))
            pygame.draw.circle(surface, (255, 255, 230), (bx, by), int(30 + 60 * k / config.BOMB_FREEZE))
        else:
            e = (k - config.BOMB_FREEZE) / config.BOMB_EXPLODE
            r = int(60 + 1100 * e ** 0.6)
            pygame.draw.circle(surface, (255, 200, 120), (bx, by), r, max(2, int(30 * (1 - e))))
            if e < 0.3:
                pygame.draw.circle(surface, (255, 240, 200), (bx, by), int(120 * (1 - e / 0.3)))

    def draw_hud(self, surface):
        f = self.app.fonts
        score = f["big"].render(str(self.rules.score), True, config.GOLD)
        surface.blit(f["big"].render(str(self.rules.score), True, (0, 0, 0)), (27, 13))
        surface.blit(score, (24, 10))
        for i in range(config.LIVES):
            alive = i < self.rules.lives
            x = 40 + i * 36
            pygame.draw.circle(surface, (0, 0, 0), (x + 2, 112), 13)
            pygame.draw.circle(surface, (230, 50, 60) if alive else (70, 50, 50), (x, 110), 13)
            if alive:
                pygame.draw.circle(surface, (255, 150, 150), (x - 4, 106), 4)
        if self.rules.streak >= config.STREAK_STEP:
            surface.blit(f["small"].render(f"streak {self.rules.streak}", True, (120, 220, 255)), (24, 134))
        if self.app.debug:
            dbg = (f"tip {self.sword.speed:5.0f} px/s  cut>={config.CUT_SPEED:.0f} (-/=)  "
                   f"blade {self.sword.length:.0f}px ([/])  t={self.elapsed:4.1f}")
            surface.blit(f["small"].render(dbg, True, config.WHITE), (10, config.HEIGHT - 56))
            for i, line in enumerate(self.app.last_events):
                surface.blit(f["small"].render(line[:70], True, config.GREY), (24, 170 + i * 24))


class PauseScene:
    """Frozen, dimmed, blurred round. Fist held 0.5 s (or P / Space) resumes with a countdown; Q quits."""

    def __init__(self, app, play, reason):
        self.app, self.play, self.reason, self.t = app, play, reason, 0.0
        snap = app.background.copy()
        play.draw(snap)
        small = pygame.transform.smoothscale(snap, (config.WIDTH // 8, config.HEIGHT // 8))
        self.snap = pygame.transform.smoothscale(small, (config.WIDTH, config.HEIGHT))
        dim = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 120))
        self.snap.blit(dim, (0, 0))

    def resume(self):
        send(self.app, {"type": "resume"})
        self.app.switch(CountdownScene(self.app, resume_to=self.play))

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_p, pygame.K_SPACE, pygame.K_RETURN):
                self.resume()
            elif event.key == pygame.K_q:
                self.play.finish("quit")
                self.app.switch(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        if self.app.fist_ready():
            self.resume()

    def draw(self, surface):
        surface.blit(self.snap, (0, 0))
        f, cx, cy = self.app.fonts, config.WIDTH // 2, config.HEIGHT // 2
        draw_text(surface, f["big"], "PAUSED", config.WHITE, (cx, cy - 90))
        why = {"hand_lost": "Can't see your hand!", "pose": "Palms up - nice and relaxed.", "key": ""}[self.reason]
        if why:
            draw_text(surface, f["small"], why, (255, 190, 120), (cx, cy - 25))
        if self.app.input_mode == "hand":
            draw_text(surface, f["mid"], f"Make a fist with your {self.app.sword_hand} hand to resume", config.GOLD, (cx, cy + 40))
            k = min(1.0, self.app.fist_time / 0.5) if self.app.fist_armed else 0.0
            pygame.draw.circle(surface, (80, 70, 60), (cx, cy + 120), 34, 6)
            if k > 0:
                pygame.draw.arc(surface, config.GOLD, (cx - 34, cy + 86, 68, 68), math.pi / 2, math.pi / 2 + k * math.tau, 6)
            draw_text(surface, f["small"], "L" if self.app.sword_hand == "left" else "R", config.WHITE, (cx, cy + 120))
        else:
            draw_text(surface, f["mid"], "P or SPACE to resume", config.GOLD, (cx, cy + 40))
        draw_text(surface, f["small"], "Q quit to title", config.WHITE, (cx, config.HEIGHT - 60))


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

    def offer(self, line):
        """The app offers every rival line here first. Only a tagged final roast for this round is taken;
        a late mid-game taunt never becomes the roast (it just shows in the bubble)."""
        if self.roast is not None or line.get("kind") != "final_roast":
            return False
        if line.get("round_id", self.app.round_id) != self.app.round_id:
            return False
        self.roast = line.get("text", "")
        self.app.rival.set_mood(line.get("mood", "gloating"), float(line.get("duration", 4.0)))
        return True

    def update(self, dt):
        self.t += dt
        if self.roast is None and self.t >= config.FINAL_ROAST_WAIT:
            self.roast = self.canned()
            self.app.rival.set_mood("gloating", 4.0)
        if self.t >= 0.8 and self.app.fist_ready():
            self.app.switch(CountdownScene(self.app))

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
            words, lines, cur = f"\"{self.roast}\"".split(), [], ""
            for w in words:
                test = (cur + " " + w).strip()
                if f["mid"].size(test)[0] > 1100 and cur:
                    lines.append(cur)
                    cur = w
                else:
                    cur = test
            lines.append(cur)
            for i, line in enumerate(lines[:4]):
                draw_text(surface, f["mid"], line, config.GOLD, (cx, 410 + i * 52))
        draw_text(surface, f["small"], ("SPACE / click / fist to play again   -   T title   -   ESC quit" if self.app.input_mode == "hand"
                   else "SPACE / click to play again   -   T title   -   ESC quit"),
                  config.WHITE, (cx, config.HEIGHT - 60))
