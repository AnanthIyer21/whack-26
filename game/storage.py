"""Best score, kept between runs on this laptop in data/game_save.json (data/ is gitignored)."""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "game_save.json")


def load_best(path=PATH):
    try:
        with open(path) as f:
            return int(json.load(f).get("best", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def save_best(score, path=PATH):
    """Saves if it's a new best. Returns True when it was."""
    if score <= load_best(path):
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"best": int(score)}, f)
        os.replace(tmp, path)
    except OSError:
        pass
    return True
