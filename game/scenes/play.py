"""The playing screen: countdown, play, auto-pause (with Quit) and resume.

Phases
  countdown - 3-2-1-GO before the run; needs a steady fist (resets if the hand drops)
  playing   - the game. If the hand isn't exactly one gripping hand, the blade freezes grey
              at once (can't cut); if that lasts PAUSE_GRACE (0.5 s) -> paused
  paused    - world frozen and dimmed, reason shown, Quit button (mouse).
              A good fist again -> resuming
  resuming  - 3-2-1 over the frozen game; hand drops -> back to paused; done -> 'resume'
When the run ends (timer, lives, or Quit) we switch to the game-over screen.
"""
import random
import time

import pygame

import shared
from .. import config as C
from ..blade import Blade
from ..boom import BombBlast, Debris
from ..combo_fx import ComboFX
from ..entities import prewarm, slice_fruit
from ..geometry import circle_hits_quad
from ..hud import Hud
from ..rival_ui import RivalDisplay
from ..scoring import Score
from ..spawner import Spawner
from ..storage import load_best, save_best
from ..ui import Button, fist_ring

PAUSE_TEXT = {"no_hand": "Show one hand", "two_hands": "Only one hand please",
              "not_gripping": "Make a fist"}


def pause_reason(s):
    if s.stale or s.hands == 0:
        return "no_hand"
    if s.hands >= 2:
        return "two_hands"
    return "not_gripping"


class PlayScene:
    def __init__(self, app):
        self.app = app
        self.ev = app.events
        prewarm()
        self.blade = Blade(app.links.blade_length)
        self.sample = None
        self.spawner = Spawner()
        self.score = Score(self.ev, lives=app.links.lives)
        self.hud = Hud(app)
        self.rival = RivalDisplay(app, 140)
        self.fx = ComboFX(app)
        self.quit_btn = Button("Quit", (C.W // 2, 560), (240, 64), danger=True)
        self.run_len = float(app.settings["seconds"])
        self.time_left = self.run_len
        self.elapsed = 0.0            # play time (excludes pauses, hit-stops and the bomb wind-up)

        self.phase = "countdown"
        self.cd = 0.0                 # countdown progress, seconds
        self.started = False          # game_start sent
        self.bad_t = 0.0              # how long the hand has been 'not good' while playing
        self.pause_reason = None
        self.warned = False
        self.ended = False
        self.pending_end = None       # "lives": end once the bomb blast has finished
        self.snapshot_next = False

        self.objects = []             # live Fruit and Bomb
        self.halves = []
        self.particles = []
        self.splats = []
        self.slashes = []
        self.debris = []
        self.blast = None
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

    def on_input_switched(self):
        self.blade.reset_history()

    def _mouse_on_quit(self):
        return self.app.input_name == "mouse" and self.phase in ("paused", "resuming") and self.quit_btn.contains_mouse()

    def handle_event(self, ev):
        if self.phase in ("paused", "resuming") and self.quit_btn.clicked(ev):
            self._end("quit")

    # ---- update ----------------------------------------------------------------------
    def update(self, dt, now):
        if self.ended:
            return
        s = self.sample = self.app.poll_input(now)
        good = s.good and not self._mouse_on_quit()
        self.rival.sync(now)
        self.hud.update(dt, self.score.points)
        self.fx.update(dt, now)
        self._close_swing(now)

        if self.phase in ("countdown", "resuming"):
            self._update_countdown(good, dt, now, s)
            self._step_effects(dt)
            return
        if self.phase == "paused":
            if good:                      # fist back: the katana reappears and a ring fills round it
                self.phase, self.cd = "resuming", 0.0
                self.blade.draw_out(now)
            self._step_effects(dt)
            return

        # ---- playing ----
        if good:
            self.bad_t = 0.0
            if self.blade.state == "frozen":
                self.blade.unfreeze()
            self.blade.update(s, now)
        else:
            self.bad_t += dt
            self.blade.freeze()           # grey, can't cut, stays where it was
            if self.bad_t >= C.PAUSE_GRACE:
                self._pause(pause_reason(s))
                return
        self._slice(now)
        self.blade.fire.set_level(self.score.multiplier)

        self.freeze_cool = max(0.0, self.freeze_cool - dt)
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        wdt = dt * self.fx.time_scale      # world time: slowed during big-combo slow motion
        self.particles = [p for p in self.particles if p.step(wdt)]
        self.debris = [d for d in self.debris if d.step(wdt)]
        if self.blast:
            if self.blast.step(dt):
                self._boom()
            if self.blast.done:
                self.blast = None
                if self.pending_end:
                    self._end(self.pending_end)
                    return
            elif self.blast.winding_up:
                return                    # world and timer frozen during the wind-up
        if self.freeze > 0:
            self.freeze -= dt
            return

        # world time
        dt = wdt
        self.elapsed += dt
        self.time_left -= dt
        if not self.warned and self.time_left <= shared.TIME_WARNING_SECONDS:
            self.warned = True
            self.ev.emit("time_warning", seconds_left=shared.TIME_WARNING_SECONDS)
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
        self.splats = [s_ for s_ in self.splats if s_.step(dt)]
        self.slashes = [s_ for s_ in self.slashes if s_.step(dt)]

    def _cd_total(self):
        return C.START_COUNTDOWN if not self.started else C.RESUME_HOLD

    def _update_countdown(self, good, dt, now, s):
        if not good:
            if self.phase == "resuming":
                self.phase = "paused"     # hand dropped before the ring filled: back to paused
                self.blade.sheathe()
            self.cd = 0.0
            return
        if self.phase == "resuming":
            self.blade.update(s, now)     # katana follows your fist while the ring fills
            self.blade.take_sweeps()      # ...but can't cut until play resumes
        self.cd += dt
        if self.cd < self._cd_total():
            return
        # GO!
        if not self.started:
            self.started = True
            self.ev.emit("game_start", duration=self.run_len, lives=self.score.lives)
        else:
            self.ev.emit("resume")
        resumed = self.phase == "resuming"
        self.phase = "playing"
        self.bad_t = 0.0
        if resumed:
            self.blade.reset_history()    # already drawn; just no slash from the old spot
        else:
            self.blade.draw_out(now)      # also clears blade history
        self.ev.emit("sword_drawn")
        if self.elapsed == 0:
            self.hud.popup("GO!", (C.W / 2, C.H / 2), (255, 230, 120), 110)

    def _step_effects(self, dt):
        """Effects that keep animating while the world is frozen (pause, countdown)."""
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        self.particles = [p for p in self.particles if p.step(dt)]
        self.debris = [d for d in self.debris if d.step(dt)]

    def _pause(self, reason):
        self.phase = "paused"
        self.pause_reason = reason
        self.ev.emit("pause", reason=reason)
        self.blade.sheathe()
        self.ev.emit("sword_sheathed")

    def _slice(self, now):
        sweeps = self.blade.take_sweeps()
        if self.blast and not self.blast.boomed:
            return                        # no cutting while the bomb winds up
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
            self.freeze = 0.04            # one tiny hit-stop per frame of cuts, not per fruit
            self.freeze_cool = 0.15

    def _fruit_cut(self, fruit, blade_angle, motion, now):
        halves, parts, splat, slash = slice_fruit(fruit, blade_angle, motion)
        self.halves += halves
        self.particles += parts
        self.splats.append(splat)
        self.slashes.append(slash)
        self.score.cut(now, fruit.kind.name)
        self.last_cut_pos = (fruit.x, fruit.y)
        self.fx.on_cut((fruit.x, fruit.y), self.score.swing, now)

    def _close_swing(self, now, finish=False):
        """Close the swing if its time is up (or the run is ending) and show any combo."""
        had = self.score.swing
        combo = self.score.finish() if finish else self.score.tick(now)
        if had and self.score.swing == 0:
            self.fx.on_swing_end(combo, now)
            if combo:
                self._combo(combo)
        return combo

    def _combo(self, combo):
        if self.freeze_cool <= 0 and combo.n >= 3:
            self.freeze, self.freeze_cool = 0.06, 0.15
        if combo.n >= 4:                   # doubles and triples don't shake the screen
            self.shake, self.shake_mag = 0.12, 2 + 1.5 * min(combo.n - 3, 4)

    def _bomb_hit(self, bomb, now):
        if self.blast:                    # a second bomb in the same swing just joins the blast
            return
        self.blast = BombBlast(bomb)
        self.freeze = 0.0
        had = self.score.swing
        lives = self.score.bomb()          # a bomb ends the swing (its combo still scores)
        if had:
            self.fx.on_swing_end(None, now)
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
        self._close_swing(time.monotonic(), finish=True)
        self.ended = True
        if self.blade.state != "sheathed":
            self.blade.sheathe()
            self.ev.emit("sword_sheathed")
        self.app.final_line = None        # so the next "final" line is this run's roast
        if self.started:
            self.ev.emit("game_over", score=self.score.points, best_combo=self.score.best_combo,
                         duration=round(self.elapsed, 1), reason=reason)
        self.result = {"score": self.score.points, "best_combo": self.score.best_combo, "reason": reason,
                       "best_before": load_best(), "new_best": save_best(self.score.points)}
        self.snapshot_next = True         # grab the last frame, then switch to game over

    # ---- draw ------------------------------------------------------------------------
    def draw(self, screen, now):
        app = self.app
        glow = app.glow
        off = (0, 0)
        if self.shake > 0:
            m = self.shake_mag * min(1.0, self.shake / 0.4)
            off = (random.uniform(-m, m), random.uniform(-m, m))

        app.background.draw(screen)
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
        self.fx.draw(screen, now)
        if self.flash > 0:
            self.flash_surf.set_alpha(int(255 * self.flash / 0.25))
            screen.blit(self.flash_surf, (0, 0))

        self.hud.draw(screen, now, self.score, self.time_left, self.run_len)
        if self.phase == "paused":
            self._draw_paused(screen)
        elif self.phase in ("countdown", "resuming"):
            self._draw_countdown(screen, now)
        self.rival.draw(screen, now, (C.W - 90, 90), C.W - 170)   # on top: it heckles your pauses

        if self.snapshot_next:
            from .gameover import GameOverScene
            app.switch_scene(GameOverScene(app, screen.copy(), self.result))

    def _draw_paused(self, screen):
        app = self.app
        self.dark_surf.set_alpha(160)
        screen.blit(self.dark_surf, (0, 0))
        cx = C.W // 2
        live = pause_reason(self.sample) if self.sample and not self.sample.good else self.pause_reason
        app.text(screen, "PAUSED", 110, (cx, 170), (255, 255, 255), "midtop", shadow=True)
        app.text(screen, PAUSE_TEXT.get(live, "Make a fist"), 60, (cx, 300), (255, 210, 90), "midtop", shadow=True)
        app.text(screen, "Close your fist to resume", 34, (cx, 380), (210, 210, 225), "midtop", shadow=True)
        self.quit_btn.draw(app, screen)

    def _draw_countdown(self, screen, now):
        app = self.app
        cx, cy = C.W // 2, C.H // 2
        if self.phase == "resuming":      # no numbers: just the ring filling round the katana
            self.dark_surf.set_alpha(70)
            screen.blit(self.dark_surf, (0, 0))
            self.blade.draw(screen, app.glow, now)     # keep the katana bright above the dim
            if self.sample is not None:
                fist_ring(screen, self.blade.base, min(1.0, self.cd / C.RESUME_HOLD), now)
            self.quit_btn.draw(app, screen)
            return
        if self.cd <= 0:
            msg = "Hold up one hand and make a fist" if not self.started else "Make a fist"
            app.text(screen, msg, 56, (cx, cy - 30), (255, 255, 255), "center", shadow=True)
        else:
            step = self._cd_total() / C.COUNTDOWN_NUMBERS
            n = C.COUNTDOWN_NUMBERS - int(self.cd / step)
            frac = (self.cd % step) / step
            size = int(200 * (1.35 - 0.35 * min(1.0, frac * 4)))
            img = app.render(str(n), size, (255, 255, 255))
            img.set_alpha(int(255 * (1 - max(0.0, frac - 0.7) / 0.3)))
            screen.blit(img, img.get_rect(center=(cx, cy)))
        if self.phase == "resuming":
            self.quit_btn.draw(app, screen)

    def debug_lines(self):
        s = self.sample
        lines = [f"phase {self.phase} bad {self.bad_t:.2f}  blade {self.blade.state}  speed {self.blade.speed:4.2f} H/s "
                 f"({'CUTS' if self.blade.speed >= C.CUT_SPEED else 'slow'})",
                 f"objects {len(self.objects)} halves {len(self.halves)} particles {len(self.particles)} "
                 f"elapsed {self.elapsed:5.1f}",
                 f"events sent {len(self.ev.log)} dropped {self.ev.dropped}  last: "
                 f"{self.ev.log[-1]['type'] if self.ev.log else '-'}"]
        if s:
            lines.append(f"hands {s.hands} grip {s.gripping} stale {s.stale} good {s.good}")
        return lines
