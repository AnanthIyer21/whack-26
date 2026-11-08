"""The full-screen webcam behind the game: cropped to 16:9, dimmed ~50% with a cool-blue tint.

The frame from shared.get_latest_frame() is RGB and already selfie-mirrored, so it lines up
with HandState.blade_base. We crop it exactly the way the Viewport maps blade_base, so the
katana comes out of your real fist on screen. Only converted when a new frame arrives
(~30 fps), so it never slows the 60 fps loop. No frame -> the fallback background.
"""
import os

import pygame

from . import config as C

TINT = (120, 135, 170)      # multiply: ~50% darker, cooler blue


def _gradient():
    surf = pygame.Surface((C.W, C.H))
    for y in range(C.H):
        u = y / C.H
        pygame.draw.line(surf, (int(20 + 15 * u), int(18 + 10 * u), int(40 + 30 * u)), (0, y), (C.W, y))
    return surf.convert()


def _fallback():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "background.png")
    if os.path.exists(path):
        try:
            img = pygame.image.load(path).convert()
            return pygame.transform.scale(img, (C.W, C.H))
        except pygame.error:
            pass
    return _gradient()


class CameraBackground:
    def __init__(self, get_latest_frame, viewport):
        self.get_latest_frame = get_latest_frame
        self.viewport = viewport
        self.fallback = _fallback()
        self.surface = None
        self.frame_t = None
        self.cam_size = None
        self.live = False

    def update(self):
        try:
            frame, t = self.get_latest_frame()
        except Exception:
            frame, t = None, 0.0
        if frame is None:
            self.live = False
            return
        self.live = True
        if t == self.frame_t and self.surface is not None:
            return
        self.frame_t = t
        h, w = frame.shape[0], frame.shape[1]
        if self.cam_size != (w, h):
            self.cam_size = (w, h)
            self.viewport.set_camera_size(w, h)
        raw = pygame.image.frombuffer(frame.tobytes(), (w, h), "RGB")
        x0, y0, cw, ch = self.viewport.crop
        area = pygame.Rect(int(x0 * w), int(y0 * h), max(1, int(cw * w)), max(1, int(ch * h)))
        cropped = raw.subsurface(area)
        if self.surface is None:
            self.surface = pygame.Surface((C.W, C.H)).convert()
        self.surface.blit(pygame.transform.scale(cropped, (C.W, C.H)), (0, 0))   # blit converts RGB -> screen format
        self.surface.fill(TINT, special_flags=pygame.BLEND_MULT)

    def draw(self, screen, off=(0, 0)):
        self.update()
        screen.blit(self.surface if self.live and self.surface is not None else self.fallback, off)
