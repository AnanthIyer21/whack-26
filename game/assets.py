"""Optional art and sound from assets/. A missing file just returns None."""
import os

import pygame

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_cache = {}


def image(name, size=None):
    """assets/<name>.png scaled to size (w, h), or None if the file isn't there."""
    key = (name, size)
    if key not in _cache:
        path = os.path.join(ROOT, name + ".png")
        img = None
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                if size:
                    img = pygame.transform.smoothscale(img, size)
            except pygame.error as e:
                print(f"[assets] couldn't load {path}: {e}")
        _cache[key] = img
    return _cache[key]
