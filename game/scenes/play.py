"""The playing screen: fruit, bombs, the katana, scoring, lives, timer and events.

Milestone 1 ends a run with a simple overlay (click or Space to play again). The title,
settings, countdown, pause and the full game-over screen come in milestone 2.
"""
import random

import pygame

from .. import config as C
from ..blade import Blade
from ..boom import BombBlast, Debris
from ..entities import prewarm, slice_fruit
from ..geometry import circle_hits_quad
from ..hud import Hud
from ..scoring import Score
from ..spawner import Spawner

TIME_WARNING_AT = 10


class PlayScene:
    def __init__(self, app):
        self.app = app
        self.ev = app.events
        prewarm()
        self.blade = Blade(app.links.blade_length)
        self.sample = None
        self.bg = _gradient()
        self.spawner = Spawner()
        self.score = Score(self.ev)
        self.hud = Hud(app)
        self.run_len = float(app.settings["seconds"])
        self.time_left = self.run_len
        self.elapsed = 0.0            # play time (excludes hit-stops and the bomb wind-up)
        self.started = False
        self.warned = False
        self.over = False
        self.end_reason = None
        self.pending_end = None       # "lives": end once the bomb blast has finished

        self.objects = []             # live Fruit and Bomb
        self.halves = []
        self.particles = []
        self.splats = []
        self.slashes = []
        self.debris = []
        self.blast = None             # the bomb sequence while it plays
        self.last_cut_pos = (C.W / 2, C.H / 2)

        self.flash_surf = pygame.Surface((C.W, C.H)).convert()   # made once: no per-frame allocation
        self.flash_surf.fill((255, 255, 255))
        self.dark_surf = pygame.Surface((C.W, C.H)).convert()
        self.dark_surf.fill((0, 0, 0))
        self.freeze = 0.0             # hit-stop: world sim paused while > 0 (input/UI keep running)
        self.freeze_cool = 0.0
        self.shake = 0.0
        self.shake_mag = 0.0
        self.flash = 0.0
        self.over_t = 0.0

    def on_input_switched(self):
        self.blade.reset_history()

    def handle_event(self, ev):
        if not self.over or self.over_t < 0.6:
            return
        if (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE) or ev.type == pygame.MOUSEBUTTONDOWN:
            self.app.switch_scene(PlayScene(self.app))

    # ---- update ----------------------------------------------------------------------
    def update(self, dt, now):
        if not self.started:
            self.started = True
            self.ev.emit("game_start")

        if self.over:
            self.over_t += dt
            self._step_effects(dt)
            return

        self._update_blade(now)
        self._slice(now)
        combo = self.score.tick(now)
        if combo:
            self._combo(combo)

        self.freeze_cool = max(0.0, self.freeze_cool - dt)
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        self.particles = [p for p in self.particles if p.step(dt)]
        self.debris = [d for d in self.debris if d.step(dt)]
        self.hud.update(dt, self.score.points)
        if self.blast:
            if self.blast.step(dt):
                self._boom()
            if self.blast.done:
                self.blast = None
                if self.pending_end:
                    self._end(self.pending_end)
                    return
            elif self.blast.winding_up:
                return                # world and timer frozen during the wind-up
        if self.freeze > 0:
            self.freeze -= dt
            return

        # world time
        self.elapsed += dt
        self.time_left -= dt
        if not self.warned and self.time_left <= TIME_WARNING_AT:
            self.warned = True
            self.ev.emit("time_warning", seconds_left=TIME_WARNING_AT)
        if self.time_left <= 0 and not self.pending_end:
            self.time_left = 0
            self._end("timer")
            return

        if not self.pending_end:
            self.objects += self.spawner.update(dt, min(self.elapsed, self.run_len), self.run_len)
        for o in self.objects:
            o.step(dt)
            if o.fell_off(o.radius):
                o.dead = True
                if not o.is_bomb:
                    self.score.miss("left" if o.x < C.W / 2 else "right")
        self.objects = [o for o in self.objects if not o.dead]
        for h in self.halves:
            h.step(dt)
        self.halves = [h for h in self.halves if not h.fell_off(h.kind.radius)]
        self.splats = [s for s in self.splats if s.step(dt)]
        self.slashes = [s for s in self.slashes if s.step(dt)]

    def _step_effects(self, dt):
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        self.particles = [p for p in self.particles if p.step(dt)]
        self.debris = [d for d in self.debris if d.step(dt)]
        for h in self.halves:
            h.step(dt)
        self.splats = [s for s in self.splats if s.step(dt)]
        self.slashes = [s for s in self.slashes if s.step(dt)]
        self.hud.update(dt, self.score.points)

    def _update_blade(self, now):
        s = self.app.input.poll(now)
        self.sample = s
        b = self.blade
        if s.good:
            if b.state == "sheathed":
                b.draw_out(now)
                self.ev.emit("sword_drawn")
            elif b.state == "frozen":
                b.unfreeze()
            b.update(s, now)
        else:
            b.freeze()
        # streak fire: the blade and trail heat up while points are doubled
        target = 1.0 if self.score.doubled else 0.0
        b.heat += (target - b.heat) * 0.1

    def _slice(self, now):
        sweeps = self.blade.take_sweeps()
        if self.blast and not self.blast.boomed:
            return                    # no cutting while the bomb winds up
        fast = [sw for sw in sweeps if sw.speed >= C.CUT_SPEED]
        if not fast:
            return
        cut_any = False
        for o in self.objects:
            if o.dead:
                continue
            r = o.hit_radius if o.is_bomb else o.radius
            for sw in fast:
                if circle_hits_quad(o.x, o.y, r, sw.quad):
                    o.dead = o.cut = True
                    if o.is_bomb:
                        self._bomb_hit(o, now)
                    else:
                        self._fruit_cut(o, sw.angle, sw.direction, now)
                        cut_any = True
                    break
        self.objects = [o for o in self.objects if not o.dead]
        if cut_any and self.freeze_cool <= 0:
            self.freeze = 0.04        # one tiny hit-stop per frame of cuts, not per fruit
            self.freeze_cool = 0.15

    def _fruit_cut(self, fruit, blade_angle, motion, now):
        halves, parts, splat, slash = slice_fruit(fruit, blade_angle, motion)
        self.halves += halves
        self.particles += parts
        self.splats.append(splat)
        self.slashes.append(slash)
        pts = self.score.cut(now, fruit.kind.name)
        self.last_cut_pos = (fruit.x, fruit.y)
        self.hud.popup(f"+{pts}", (fruit.x, fruit.y - fruit.radius),
                       (255, 180, 80) if pts > 1 else (255, 255, 255), 30)

    def _combo(self, n):
        x, y = self.last_cut_pos
        x = max(160, min(C.W - 160, x))
        y = max(140, min(C.H - 80, y))
        self.hud.popup(f"{n}x COMBO  +{n}", (x, y - 50), (255, 220, 80), 52)
        if self.freeze_cool <= 0:
            self.freeze, self.freeze_cool = 0.08, 0.15
        self.shake, self.shake_mag = 0.15, 5

    def _bomb_hit(self, bomb, now):
        if self.blast:                # a second bomb in the same swing just joins the blast
            return
        self.blast = BombBlast(bomb)
        self.freeze = 0.0
        lives = self.score.bomb()
        self.hud.life_lost(lives, now)
        if lives == 0:
            self.pending_end = "lives"

    def _boom(self):
        """The bomb goes off: flash, shake, and blast everything off the screen."""
        b = self.blast
        self.particles += b.boom_particles()
        self.shake, self.shake_mag = 0.5, 18
        self.flash = 0.25
        for o in self.objects + self.halves:      # blasted fruit score nothing and aren't misses
            self.debris.append(Debris(o.image(), o.x, o.y, o.rot, b.x, b.y))
        self.objects.clear()
        self.halves.clear()
        self.spawner.timer = max(self.spawner.timer, 1.0)   # a moment of calm after the boom
        self.spawner.queue.clear()

    def _end(self, reason):
        combo = self.score.finish()
        if combo:
            self._combo(combo)
        self.over = True
        self.end_reason = reason
        self.blade.sheathe()
        self.ev.emit("sword_sheathed")
        self.ev.emit("game_over", score=self.score.points, best_combo=self.score.best_combo,
                     duration=round(self.elapsed, 1), reason=reason)

    # ---- draw ------------------------------------------------------------------------
    def draw(self, screen, now):
        glow = self.app.glow
        off = (0, 0)
        if self.shake > 0:
            m = self.shake_mag * min(1.0, self.shake / 0.4)
            off = (random.uniform(-m, m), random.uniform(-m, m))

        screen.blit(self.bg, (0, 0))
        for s in self.splats:
            s.draw(screen, off)
        for h in self.halves:
            h.draw(screen, off)
        for o in self.objects:
            if o.is_bomb:
                o.draw(screen, off, glow, now)
            else:
                o.draw(screen, off)
        for d in self.debris:
            d.draw(screen, off)
        for p in self.particles:
            p.draw(glow, off)
        for s in self.slashes:
            s.draw(glow, off)
        if self.blast:
            self.blast.draw(screen, glow, self.dark_surf, off)
        self.blade.draw(screen, glow, now)
        screen.blit(glow, (0, 0))

        if self.flash > 0:
            self.flash_surf.set_alpha(int(255 * self.flash / 0.25))
            screen.blit(self.flash_surf, (0, 0))

        self.hud.draw(screen, now, self.score, self.time_left, self.run_len)
        if self.over:
            self._draw_over(screen)
        else:
            self.app.text(screen, "Hold left mouse = fist, swing to slice.  0/1/2 fake hand count.  "
                          "F fullscreen  D debug  Tab mouse/hand", 20, (C.W // 2, C.H - 10),
                          (150, 150, 160), "midbottom")

    def _draw_over(self, screen):
        u = min(1.0, self.over_t / 0.4)
        self.dark_surf.set_alpha(int(150 * u))
        screen.blit(self.dark_surf, (0, 0))
        title = {"timer": "TIME'S UP", "lives": "OUT OF LIVES", "quit": "QUIT"}[self.end_reason]
        cx = C.W // 2
        self.app.text(screen, title, 96, (cx, 220), (255, 255, 255), "midtop")
        self.app.text(screen, f"Score  {self.score.points}", 64, (cx, 320), (255, 220, 80), "midtop")
        self.app.text(screen, f"Best combo  {self.score.best_combo}", 40, (cx, 390), (220, 220, 230), "midtop")
        if self.over_t > 0.6:
            self.app.text(screen, "Click or press Space to play again", 32, (cx, 470), (190, 190, 200), "midtop")

    def debug_lines(self):
        s = self.sample
        lines = [f"blade {self.blade.state}  speed {self.blade.speed:4.2f} H/s "
                 f"({'CUTS' if self.blade.speed >= C.CUT_SPEED else 'slow'})",
                 f"objects {len(self.objects)} halves {len(self.halves)} particles {len(self.particles)} "
                 f"elapsed {self.elapsed:5.1f}",
                 f"events sent {len(self.ev.log)} dropped {self.ev.dropped}  last: "
                 f"{self.ev.log[-1]['type'] if self.ev.log else '-'}"]
        if s:
            lines.append(f"hands {s.hands} grip {s.gripping} stale {s.stale} good {s.good}")
        return lines


def _gradient():
    surf = pygame.Surface((C.W, C.H))
    for y in range(C.H):
        u = y / C.H
        pygame.draw.line(surf, (int(20 + 15 * u), int(18 + 10 * u), int(40 + 30 * u)), (0, y), (C.W, y))
    return surf.convert()
