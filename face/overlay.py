"""--facedebug: a live face-debug panel drawn on top of the game window.

It doesn't touch the game's code: main.py installs it by wrapping
pygame.display.flip, so just before each frame is shown we draw the panel onto
the display surface. Main thread only (that's where flip is called).

Per expression: a bar for its level (the white tick is the threshold: past it
means "on"), and a hold meter (fills while held; full = fires). Below: state and
the last few steps of the face pipeline (fired -> received -> waiting / dropped / spoken).
"""

import time

import pygame

import shared
from face import config as C

PANEL_W = 470
ROW_H = 22
BAR_W = 160
_font = None
_real_flip = None


def install():
    global _real_flip
    if _real_flip is not None:
        return
    _real_flip = pygame.display.flip

    def flip_with_panel(*args, **kwargs):
        try:
            surface = pygame.display.get_surface()
            if surface is not None:
                draw(surface)
        except Exception as exc:          # the debug panel must never break the game
            print("[facedebug] overlay error: " + repr(exc))
        return _real_flip(*args, **kwargs)

    pygame.display.flip = flip_with_panel


def _text(surface, text, pos, colour=(235, 235, 245)):
    global _font
    if _font is None:
        _font = pygame.font.Font(None, 22)
    surface.blit(_font.render(text, True, colour), pos)


def draw(surface):
    import face
    d = face.diag
    fs = shared.get_face_state()
    rows = len(C.PRIORITY) + 3
    height = ROW_H * rows + 18 * len(face.debug_log) + 14
    x0, y0 = 10, surface.get_height() - 10 - height
    panel = pygame.Surface((PANEL_W, height), pygame.SRCALPHA)
    panel.fill((10, 10, 20, 205))
    surface.blit(panel, (x0, y0))

    state = str(d.get("state"))
    calibrated = "calibrated" if d.get("calibrated") else "CALIBRATING (5 s)"
    _text(surface, "FACE DEBUG  %.1f fps  %.0f ms  faces=%d  %s" % (
        d.get("fps", 0.0), d.get("ms", 0.0), d.get("faces", 0), calibrated), (x0 + 8, y0 + 6), (255, 220, 120))
    _text(surface, "state: " + state + "   held: " + fs.expression + "   turn %+.0f  tilt %+.0f" % (fs.yaw, fs.pitch),
          (x0 + 8, y0 + 6 + ROW_H))

    y = y0 + 6 + ROW_H * 2
    levels = d.get("levels", {})
    holds = d.get("holds", {})
    armed = d.get("armed", {})
    for name in C.PRIORITY:
        level = levels.get(name)
        enabled = name in C.ENABLED_EXPRESSIONS
        colour = (235, 235, 245) if enabled else (120, 120, 130)
        _text(surface, name, (x0 + 8, y), colour)
        bx = x0 + 120
        pygame.draw.rect(surface, (60, 60, 75), (bx, y + 3, BAR_W, 12))
        if level is not None:
            # map level -0.5..+0.3 onto the bar; threshold (0) sits at 62.5%
            frac = max(0.0, min(1.0, (level + 0.5) / 0.8))
            fill = (90, 220, 120) if level >= 0 else (200, 140, 60)
            pygame.draw.rect(surface, fill, (bx, y + 3, int(BAR_W * frac), 12))
        tick = bx + int(BAR_W * 0.625)
        pygame.draw.line(surface, (255, 255, 255), (tick, y), (tick, y + 18), 2)
        hx = bx + BAR_W + 10
        pygame.draw.rect(surface, (60, 60, 75), (hx, y + 3, 60, 12))
        pygame.draw.rect(surface, (120, 170, 255), (hx, y + 3, int(60 * holds.get(name, 0.0)), 12))
        tag = "" if armed.get(name, True) else " used"
        lv = "--" if level is None else "%+.2f" % level
        _text(surface, lv + tag, (hx + 68, y), colour)
        y += ROW_H

    now = time.monotonic()
    for t, text in list(face.debug_log):
        age = now - t
        colour = (150, 255, 170) if "SPOKEN" in text else (255, 150, 150) if "drop" in text else (210, 210, 230)
        _text(surface, "%4.0fs ago  %s" % (age, text[:62]), (x0 + 8, y), colour)
        y += 18
