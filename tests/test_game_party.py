"""Party mode + leaderboards (RBadiadka7)."""
import os
import queue

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from game.leaderboard import Party, Store, unique_names  # noqa: E402


def setup_module():
    pygame.init()
    pygame.display.set_mode((1, 1))


def key(k, ch=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0)


def test_alltime_keeps_top_10_and_qualifies():
    s = Store(":memory:")
    assert not s.qualifies(0) and s.qualifies(5)
    for i in range(1, 13):
        s.add_alltime(f"p{i}", i * 10)
    top = s.top()
    assert len(top) == 10 and top[0] == ("p12", 120) and top[-1][1] == 30
    assert not s.qualifies(30) and s.qualifies(31)


def test_names_blank_and_duplicates():
    assert unique_names(["", "Ananth", "ananth", "  Aaron  "]) == ["Player 1", "Ananth", "ananth 2", "Aaron"]


def test_party_best_score_counts_and_wipes():
    s = Store(":memory:")
    p = Party(["A", "B", "C"], s)
    p.record(100, 3)
    p.record(300, 5)
    assert p.standings()[-1] == (3, "C", None) and not p.round_done
    p.record(100, 1)
    assert p.round_done
    p.next_round()
    p.record(500, 9)                                  # A improves
    st = p.standings()
    assert st[0] == (1, "A", 500) and st[1] == (2, "B", 300) and st[2] == (3, "C", 100)
    assert s.top()[0] == ("A", 500)
    p.end()
    assert s.party_best() == {}
    assert s.last_names() == ["A", "B", "C"]


def _app():
    from game.link import resolve
    from game.app import App
    app = App(resolve(post_event=lambda e: None, rival_lines=queue.Queue()))
    app.leaderboard = Store(":memory:")
    return app


def _finish_turn(app, points):
    import game.scenes.play as play
    from game.scenes.play import PlayScene
    play.load_best, play.save_best = (lambda: 0), (lambda score: False)   # don't touch data/game_save.json
    from game.scenes.gameover import GameOverScene
    sc = PlayScene(app)
    sc.started = True
    sc.score.points = points
    sc._end("timer")
    over = GameOverScene(app, pygame.Surface((1280, 720)), sc.result)
    over.draw(pygame.Surface((1280, 720)), 1.0)
    return over


def test_full_party_flow_draws_every_screen():
    from game.scenes.title import TitleScene
    from game.scenes.party import LeaderboardScene, NextUpScene, PartySetupScene
    app = _app()
    screen = pygame.Surface((1280, 720))
    title = TitleScene(app)
    app.scene = title
    title.handle_event(key(pygame.K_p, "p"))
    setup = app.scene
    assert isinstance(setup, PartySetupScene) and setup.typing
    setup.count = 2
    for b in setup.boxes:
        b.text = ""
    for ch in "Fred":                                 # F is a letter here, not fullscreen
        setup.handle_event(key(getattr(pygame, "K_" + ch.lower()), ch))
    setup.handle_event(key(pygame.K_RETURN))
    for ch in "Di":
        setup.handle_event(key(getattr(pygame, "K_" + ch.lower()), ch))
    setup.draw(screen, 0.0)
    setup.handle_event(key(pygame.K_RETURN))         # Enter on the last box starts
    assert isinstance(app.scene, NextUpScene) and app.party.names == ["Fred", "Di"]
    app.scene.draw(screen, 0.0)

    over = _finish_turn(app, 120)
    assert over.again_btn.label == "Next player" and over.player == "Fred"
    over._again()
    assert isinstance(app.scene, NextUpScene) and app.party.current == "Di"
    over = _finish_turn(app, 340)
    assert over.again_btn.label == "Leaderboard"
    over._again()
    board = app.scene
    assert isinstance(board, LeaderboardScene)
    assert board.rows == [(1, "Di", 340), (2, "Fred", 120)]
    board.t = 5.0
    board.draw(screen, 1.0)
    board.handle_event(key(pygame.K_ESCAPE))         # End party
    assert app.party is None and app.leaderboard.party_best() == {}
    assert app.leaderboard.top() == [("Di", 340), ("Fred", 120)]


def test_solo_top10_name_entry():
    app = _app()
    over = _finish_turn(app, 250)
    assert over.typing and app.party is None
    for ch in "zed":
        over.handle_event(key(getattr(pygame, "K_" + ch), ch))
    over.handle_event(key(pygame.K_SPACE, " "))      # space types, doesn't replay
    over.handle_event(key(pygame.K_RETURN))
    assert not over.typing and app.leaderboard.top() == [("zed", 250)]
    over.draw(pygame.Surface((1280, 720)), 2.0)
    assert not _finish_turn(app, 0).typing           # zero never qualifies
