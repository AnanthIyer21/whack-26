import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from game.entities import KINDS, Fruit, Bomb, slice_fruit  # noqa: E402


def setup_module():
    pygame.init()
    pygame.display.set_mode((1, 1))


def test_cut_line_follows_blade_not_motion():
    f = Fruit(KINDS[2], (400, 300), (0, 0), 0, 0)
    blade = math.radians(-60)
    halves, *_ = slice_fruit(f, blade, (1.0, 0.0))        # moving right, blade tilted
    # halves separate perpendicular to the blade line
    ux, uy = math.cos(blade), math.sin(blade)
    for h in halves:
        rel_vx = h.vx - 0.0 - 50 * 1.0                        # remove the motion push
        rel_vy = h.vy - 0.0
        along = rel_vx * ux + rel_vy * uy
        across = abs(-rel_vx * uy + rel_vy * ux)
        assert across > 100 and abs(along) < 1e-6
    # the slash streak lies along the blade
    slash = slice_fruit(f, blade, (1.0, 0.0))[3]
    assert abs(slash.d[0] - ux) < 1e-9 and abs(slash.d[1] - uy) < 1e-9


def test_bomb_blast_clears_screen_without_misses():
    from game.link import resolve
    from game.app import App
    from game.scenes.play import PlayScene
    app = App(resolve(post_event=lambda e: None))
    sc = PlayScene(app)
    sc.objects = [Fruit(KINDS[i], (200 + 100 * i, 400), (0, 0), 0, 0) for i in range(5)]
    bomb = Bomb((640, 360), (0, 0), 0, 0)
    sc._bomb_hit(bomb, 0.0)
    for _ in range(40):                                  # ~0.67 s: through wind-up and boom
        if sc.blast and sc.blast.step(1 / 60):
            sc._boom()
    assert sc.objects == [] and sc.halves == []
    assert len(sc.debris) == 5
    assert "miss" not in app.events.types()


def _scene_with(objs):
    import queue
    from game.link import resolve
    from game.app import App
    from game.scenes.play import PlayScene
    app = App(resolve(post_event=lambda e: None, rival_lines=queue.Queue()))
    sc = PlayScene(app)
    sc.phase, sc.started = "playing", True
    sc.objects = objs
    return sc


def _sweep(speed, lag):
    from game.blade import Sweep
    # a horizontal slash along y = 300 from x = 200 to 900
    return Sweep([(200, 300), (200, 299), (900, 299), (900, 300)], speed, (1.0, 0.0), -math.pi / 2, lag)


def test_lag_sweep_gives_fruit_room_for_error():
    from game import config as Cfg
    k = KINDS[2]                                   # orange, radius 40
    off = k.radius + 30                            # 30 px beyond touching the slash
    for lag, expect in ((False, False), (True, True)):
        sc = _scene_with([Fruit(k, (500, 300 + off), (0, 0), 0, 0)])
        sc.blade._pending = [_sweep(Cfg.CUT_SPEED * 1.5, lag)]
        sc._slice(0.0)
        assert (sc.objects == []) == expect, lag


def test_lag_sweep_lower_speed_bar():
    from game import config as Cfg
    for lag, expect in ((False, False), (True, True)):
        sc = _scene_with([Fruit(KINDS[2], (500, 300), (0, 0), 0, 0)])
        sc.blade._pending = [_sweep(Cfg.CUT_SPEED * 0.75, lag)]
        sc._slice(0.0)
        assert (sc.objects == []) == expect, lag


def test_lag_sweep_is_kinder_with_bombs():
    from game import config as Cfg
    near = Bomb((500, 300), (0, 0), 0, 0).hit_radius * 0.85   # grazing distance
    for lag, expect_hit in ((False, True), (True, False)):
        sc = _scene_with([Bomb((500, 300 + near), (0, 0), 0, 0)])
        sc.blade._pending = [_sweep(Cfg.CUT_SPEED * 1.5, lag)]
        sc._slice(0.0)
        assert (sc.blast is not None) == expect_hit, lag
