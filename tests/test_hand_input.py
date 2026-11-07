import time

from game import bridge, fakes
from game.input import HandInput


def setup_module():
    bridge.setup()


def test_new_sample_only_when_t_changes_and_pixels_mapped():
    fakes.set_hand_state(sword_visible=True, sword_active=True, blade_base=(0.5, 0.25), blade_angle=-1.0)
    h = HandInput()
    s1 = h.update(1 / 60)
    assert s1.new and s1.active and s1.visible
    assert s1.base == (640.0, 180.0) and s1.angle == -1.0
    s2 = h.update(1 / 60)          # vision hasn't published again
    assert not s2.new and s2.active


def test_stale_state_counts_as_lost_and_sheathes():
    fakes.set_hand_state(sword_visible=True, sword_active=True)
    fakes._state.t -= 1.0          # pretend the last frame is a second old
    h = HandInput()
    s = h.update(1 / 60)
    assert not s.visible and not s.active
    time.sleep(0.05)
    assert h.lost_for >= 0.04


def test_pause_pose_and_recovery():
    fakes.set_hand_state(sword_visible=True, sword_active=False, pause_pose=True)
    h = HandInput()
    h.update(1 / 60)
    assert h.pause_pose and h.lost_for == 0.0
    fakes.set_hand_state(pause_pose=False)
    h.update(1 / 60)
    assert not h.pause_pose
