"""Fake game: a pygame window that shows every interface working.

- Initialises the mixer exactly as the real game must (shared constants, channel 0 reserved).
- Draws the camera preview, the blade (using the shared angle convention), the HandState
  fields, the auto-pause state, the latest rival line, and a DUCKING indicator.
- Posts a scripted run of every event type to shared.events, looping.
- Mouse mode: publishes shared.mouse_hand_state() every frame (hold the button = grip).
"""

import math
import time

import pygame

import shared

WIDTH = 960
HEIGHT = 540

# (seconds after the previous event, event builder)
SCRIPT = (
    (1.0, lambda: shared.ev_game_start(shared.DEFAULT_RUN_SECONDS, shared.LIVES)),
    (0.5, shared.ev_sword_drawn),
    (1.0, lambda: shared.ev_slice("apple")),
    (0.6, lambda: shared.ev_slice("melon")),
    (1.0, lambda: shared.ev_miss("left")),
    (1.0, lambda: shared.ev_combo(4)),
    (1.0, lambda: shared.ev_streak(5)),
    (1.5, lambda: shared.ev_streak_broken(5)),
    (1.5, shared.ev_bomb_hit),
    (0.1, lambda: shared.ev_life_lost(2)),
    (2.0, lambda: shared.ev_pause("not_gripping")),
    (2.5, shared.ev_resume),
    (2.0, lambda: shared.ev_miss("right")),
    (2.0, lambda: shared.ev_time_warning(shared.TIME_WARNING_SECONDS)),
    (2.0, shared.ev_sword_sheathed),
    (0.5, lambda: shared.ev_game_over(140, 4, 60.0, "timer")),
)
LOOP_GAP = 4.0


def pause_reason(hand):
    """The auto-pause rule from the spec. None means 'playing'."""
    if hand.hands_in_frame == 0:
        return "no_hand"
    if hand.hands_in_frame >= 2:
        return "two_hands"
    if not hand.sword_active:
        return "not_gripping"
    return None


def blade_tip_px(hand):
    """Shared convention: length is a fraction of screen height, y points down."""
    base_x = hand.blade_base[0] * WIDTH
    base_y = hand.blade_base[1] * HEIGHT
    length = shared.BLADE_LENGTH * HEIGHT
    tip_x = base_x + length * math.cos(hand.blade_angle)
    tip_y = base_y + length * math.sin(hand.blade_angle)
    return (base_x, base_y), (tip_x, tip_y)


def run(stop_event, mouse_sword=False):
    pygame.mixer.pre_init(shared.MIXER_FREQ, shared.MIXER_SIZE, shared.MIXER_CHANNELS, shared.MIXER_BUFFER)
    pygame.init()
    pygame.mixer.set_reserved(1)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("WHACK 26 skeleton (fake game)")
    # Built-in font: pygame.font.SysFont hangs for seconds on macOS (it shells out to X11 fc-list).
    font = pygame.font.Font(None, 22)
    big = pygame.font.Font(None, 30)
    clock = pygame.time.Clock()

    script_index = 0
    next_event_at = time.monotonic() + SCRIPT[0][0]
    bubble = None
    bubble_until = 0.0
    fps_text = ""

    while not stop_event.is_set():
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                return

        now = time.monotonic()

        if mouse_sword:
            mx, my = pygame.mouse.get_pos()
            pressed = pygame.mouse.get_pressed()[0]
            shared.set_hand_state(shared.mouse_hand_state(mx / WIDTH, my / HEIGHT, pressed, now))

        # Scripted events (never blocks).
        if now >= next_event_at:
            builder = SCRIPT[script_index][1]
            shared.post_event(builder())
            script_index += 1
            if script_index >= len(SCRIPT):
                script_index = 0
                next_event_at = now + LOOP_GAP + SCRIPT[0][0]
            else:
                next_event_at = now + SCRIPT[script_index][0]

        # Drain rival lines; show only the newest.
        while True:
            try:
                line = shared.rival_lines.get_nowait()
            except Exception:
                break
            bubble = line
            bubble_until = now + line["duration"]

        # --- draw ---
        frame, frame_t = shared.get_latest_frame()
        if frame is not None:
            h = frame.shape[0]
            w = frame.shape[1]
            surf = pygame.image.frombuffer(frame.tobytes(), (w, h), "RGB")
            screen.blit(pygame.transform.scale(surf, (WIDTH, HEIGHT)), (0, 0))
        else:
            screen.fill((40, 40, 48))

        hand = shared.get_hand_state()
        reason = pause_reason(hand)
        if hand.sword_visible:
            base, tip = blade_tip_px(hand)
            colour = (240, 240, 255) if reason is None else (120, 120, 140)
            pygame.draw.line(screen, colour, base, tip, 6)
            pygame.draw.circle(screen, (255, 200, 60), (int(base[0]), int(base[1])), 10)

        age_ms = (now - hand.t) * 1000.0 if hand.t > 0 else -1
        info = (
            "sword_visible  " + str(hand.sword_visible),
            "sword_active   " + str(hand.sword_active),
            "blade_base     (" + str(round(hand.blade_base[0], 2)) + ", " + str(round(hand.blade_base[1], 2)) + ")",
            "blade_angle    " + str(round(hand.blade_angle, 2)),
            "hands_in_frame " + str(hand.hands_in_frame),
            "confidence     " + str(round(hand.confidence, 2)),
            "state age      " + str(round(age_ms)) + " ms",
            fps_text,
        )
        y = 10
        for text in info:
            screen.blit(font.render(text, True, (255, 255, 255)), (10, y))
            y += 20

        if reason is not None:
            label = big.render("PAUSED: " + reason, True, (255, 90, 90))
            screen.blit(label, (WIDTH // 2 - label.get_width() // 2, 20))

        if shared.rival_speaking.is_set():
            screen.blit(font.render("DUCKING (rival speaking)", True, (255, 220, 0)), (WIDTH - 260, 10))

        if bubble is not None and now < bubble_until:
            prefix = "[FINAL] " if bubble.get("final") else ""
            text = prefix + "GRIP-9000 (" + bubble["mood"] + "): " + bubble["text"]
            label = big.render(text, True, (20, 20, 20))
            box = pygame.Rect(20, HEIGHT - 70, label.get_width() + 20, 44)
            pygame.draw.rect(screen, (255, 255, 255), box, border_radius=10)
            screen.blit(label, (30, HEIGHT - 60))

        pygame.display.flip()
        # tick() oversleeps on macOS (~45 fps); tick_busy_loop holds 60.
        clock.tick_busy_loop(shared.FPS)
        fps_text = "fps            " + str(round(clock.get_fps()))
