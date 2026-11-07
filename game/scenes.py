"""The game's screens. Each scene has handle(event), update(dt) and draw(surface)."""
import pygame

from game import bridge, config


def draw_text(surface, font, text, colour, center):
    img = font.render(text, True, colour)
    surface.blit(img, img.get_rect(center=center))


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

    def start(self):
        print(f"[title] start with sword hand = {self.app.sword_hand}")  # countdown comes in step 2

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_l:
                self.choose("left")
            elif event.key == pygame.K_r:
                self.choose("right")
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.start()
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
