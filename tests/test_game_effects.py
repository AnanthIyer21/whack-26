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
    app = App(resolve(start_rival_if_fake=False))
    sc = app.scene
    sc.objects = [Fruit(KINDS[i], (200 + 100 * i, 400), (0, 0), 0, 0) for i in range(5)]
    bomb = Bomb((640, 360), (0, 0), 0, 0)
    sc._bomb_hit(bomb, 0.0)
    for _ in range(40):                                  # ~0.67 s: through wind-up and boom
        if sc.blast and sc.blast.step(1 / 60):
            sc._boom()
    assert sc.objects == [] and sc.halves == []
    assert len(sc.debris) == 5
    assert "miss" not in app.events.types()
