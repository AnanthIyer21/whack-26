"""Replays the dropout from the IMG_9595 clip: a fast swing, vision's hold, a full dropout,
then the hand found further along. The katana should keep flying, never teleport, stay armed,
and cut fruit that were in the swing's path during the dropout."""
import math

import shared
from game import config as C
from game.blade import Blade
from game.geometry import circle_hits_quad
from game.input import HandInput, Viewport

FPS_CAM = 30
LATENCY = 0.03


def make_stream(swing_speed=1.6, held=(0.20, 0.35), lost=(0.35, 0.50), back_x=0.85, end=0.75):
    """HandState over time: normalised x moves right at swing_speed (widths/s) while tracked."""
    states = []
    conf = 0.80
    x = 0.20
    t = 0.0
    while t <= end:
        if t < held[0]:
            x = 0.20 + swing_speed * t
            conf = 0.80 + 0.01 * math.sin(t * 97)          # real detections jitter
            states.append(shared.HandState(True, True, (x, 0.6), -math.pi / 2, 1, "none", conf, t))
        elif t < held[1]:
            x += 0.002                                      # vision's coast barely moves it
            states.append(shared.HandState(True, True, (x, 0.6), -math.pi / 2, 1, "none", conf, t))
        elif t < lost[1]:
            states.append(shared.HandState(False, False, (x, 0.6), -math.pi / 2, 0, "none", 0.0, t))
        else:
            back = back_x + 0.3 * (t - lost[1])
            conf = 0.82 + 0.01 * math.sin(t * 53)
            states.append(shared.HandState(True, True, (back, 0.6), -math.pi / 2, 1, "none", conf, t))
        t += 1 / FPS_CAM
    return states


def run(states, fruit=None):
    cur = {"s": shared.HandState()}
    inp = HandInput(lambda: cur["s"], Viewport())
    blade = Blade(0.25)
    blade.draw_out(-1.0)
    outs, cut = [], False
    now = states[0].t + LATENCY
    i = 0
    while now < states[-1].t + LATENCY:
        while i < len(states) and states[i].t + LATENCY <= now:
            cur["s"] = states[i]
            i += 1
        s = inp.poll(now)
        outs.append((now, s))
        if s.good:
            if blade.state == "frozen":
                blade.unfreeze()
            blade.update(s, now)
        else:
            blade.freeze()
        for sw in blade.take_sweeps():
            if fruit and sw.speed >= C.CUT_SPEED and circle_hits_quad(fruit[0], fruit[1], 30, sw.quad):
                cut = True
        now += 1 / 60
    return outs, cut, inp


def test_held_frames_are_detected():
    states = make_stream()
    outs, _, inp = run(states)
    assert inp.predictor.predictions >= 1


def test_blade_keeps_flying_through_the_dropout_and_never_teleports():
    outs, _, _ = run(make_stream())
    xs = [s.base[0] for _, s in outs if s.good]
    jumps = [abs(b - a) for a, b in zip(xs, xs[1:])]
    assert max(jumps) < 90, max(jumps)                       # no teleport (the old code jumped ~400 px)
    # during the dropout the blade carried on well past where tracking stopped (x ~ 0.52 W)
    mid = [s.base[0] for t, s in outs if 0.30 + LATENCY <= t <= 0.45 + LATENCY]
    assert max(mid) > 0.62 * C.W


def test_stays_armed_so_no_grey_blade_during_short_dropout():
    outs, _, _ = run(make_stream())
    assert all(s.good for t, s in outs if t >= 0.1)


def test_fruit_in_the_swing_path_during_the_dropout_gets_cut():
    # in the path, between where tracking was lost (~0.52 W) and where it came back (0.85 W)
    _, cut, _ = run(make_stream(), fruit=(0.68 * C.W, 0.6 * C.H - 0.12 * C.H))
    assert cut


def test_slow_movement_is_not_predicted():
    outs, _, inp = run(make_stream(swing_speed=0.05, back_x=0.30))
    assert inp.predictor.predictions == 0


def test_open_hand_mid_swing_is_not_predicted():
    states = make_stream()
    # replace the dropout with a clearly visible OPEN hand (hands=1, not gripping)
    states = [shared.HandState(True, False, s.blade_base, s.blade_angle, 1, "none", 0.7, s.t)
              if 0.20 <= s.t < 0.50 else s for s in states]
    outs, _, inp = run(states)
    assert inp.predictor.predictions == 0
    assert any(not s.good for t, s in outs if 0.25 + LATENCY < t < 0.45 + LATENCY)


def test_end_to_end_teleport_cuts_fruit_where_it_was_when_the_blade_passed():
    """Through the real play scene: a slow move (nothing to predict), the hand is lost for
    0.45 s and reappears far to the right - a teleport. A fruit crossed that path halfway
    through the gap but has shot 220 px up since. It must still be cut (time-matched check)."""
    import os, queue
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from game.app import App
    from game.entities import KINDS, Fruit
    from game.link import resolve
    from game.scenes.play import PlayScene

    states = make_stream(swing_speed=0.1, held=(0.20, 0.30), lost=(0.30, 0.75), back_x=0.85, end=1.0)
    cur = {"s": shared.HandState()}
    app = App(resolve(post_event=lambda e: None, rival_lines=queue.Queue(),
                      get_hand_state=lambda: cur["s"]), input_mode="hand")
    sc = PlayScene(app)
    sc.phase, sc.started = "playing", True
    sc.blade.draw_out(-1.0)
    sc.spawner.timer = 999
    # on the blade's straight path (x = 0.6 W, blade band y 252..432) at ~t = 0.56,
    # rising at 1000 px/s, so by the time tracking returns it's well above the band
    t_pass = 0.56
    f = Fruit(KINDS[2], (0.60 * C.W, 340 + 1000 * (t_pass - LATENCY)), (0, -1000), 0, 0)
    sc.objects = [f]
    now, i = states[0].t + LATENCY, 0
    while now < states[-1].t + LATENCY:
        while i < len(states) and states[i].t + LATENCY <= now:
            cur["s"] = states[i]
            i += 1
        sc.update(1 / 60, now)
        now += 1 / 60
    assert app.inputs["hand"].predictor.predictions == 0     # a teleport, not a predicted swing
    assert f.cut, "fruit that crossed the teleport path during the gap was missed"
