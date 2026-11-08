"""The line bank: instant, pre-voiced lines for every moment.

Templates in lines.json may contain {side} or {n}. Every allowed value is listed
in _expand / _expand_by_key, so every concrete line can be voiced ahead of time.
A line whose variable value was not pre-voiced (e.g. a combo of 9) is simply not
eligible; another line in the same list is used instead.

No repeats: each list is a shuffled deck; a line comes back only after the rest.
"""

import json
import os
import random
import re

LINES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lines.json")
_VAR = re.compile(r"\{(\w+)\}")


def bank_key(decision_key, mood, vars_):
    """Which list in lines.json a timing Decision should draw from."""
    if decision_key == "pause":
        return "pause." + vars_.get("reason", "not_gripping")
    if decision_key == "pattern":
        return "pattern." + vars_.get("pattern", "slump")
    if decision_key == "game_over":
        if vars_.get("new_best"):
            return "game_over.new_best"
        return "game_over." + vars_.get("reason", "timer")
    if decision_key in ("face", "face_combo"):
        expression = vars_.get("expression", "smiling")
        if mood == "rattled" and expression in ("smiling", "laughing"):
            return "face." + expression + ".rattled"
        return "face." + expression
    if decision_key == "time_warning":
        if mood == "rattled":
            return "time_warning.rattled"
        return "time_warning.gloating"
    return decision_key


class Bank:
    def __init__(self, path=LINES_PATH, rng=None):
        with open(path) as f:
            data = json.load(f)
        self.rng = rng if rng is not None else random.Random()
        self.expand = data.get("_expand", {})
        self.expand_by_key = data.get("_expand_by_key", {})
        self.templates = {}
        for key in data:
            if not key.startswith("_"):
                self.templates[key] = data[key]
        self.decks = {}

    def keys(self):
        return list(self.templates)

    def allowed(self, key, var):
        by_key = self.expand_by_key.get(key.split(".")[0], {})
        if var in by_key:
            return by_key[var]
        return self.expand.get(var, [])

    def expand_template(self, key, template):
        """Every concrete text this template can produce: list of (text, vars)."""
        names = []
        for name in _VAR.findall(template):
            if name not in names:
                names.append(name)
        results = [(template, {})]
        for name in names:
            next_results = []
            for text, vars_ in results:
                for value in self.allowed(key, name):
                    filled = dict(vars_)
                    filled[name] = value
                    next_results.append((text.replace("{" + name + "}", str(value)), filled))
            results = next_results
        return results

    def all_texts(self):
        """Every concrete line, for voicing. Returns list of (key, text)."""
        out = []
        seen = set()
        for key in self.templates:
            for template in self.templates[key]:
                for text, vars_ in self.expand_template(key, template):
                    if text not in seen:
                        seen.add(text)
                        out.append((key, text))
        return out

    def pick(self, key, vars_):
        """A concrete line for this list, honouring vars, without repeats. None if nothing fits."""
        templates = self.templates.get(key)
        if not templates:
            return None
        eligible = []
        for template in templates:
            text = self._fill(key, template, vars_)
            if text is not None:
                eligible.append(text)
        if not eligible:
            return None
        deck = self.decks.get(key)
        if deck is None or not deck:
            deck = list(range(len(templates)))
            self.rng.shuffle(deck)
            self.decks[key] = deck
        # Walk the deck for the first template that fits these vars.
        tries = len(deck)
        while tries > 0:
            index = deck.pop(0)
            text = self._fill(key, templates[index], vars_)
            if text is not None:
                return text
            deck.append(index)
            tries -= 1
        return eligible[0]

    def _fill(self, key, template, vars_):
        text = template
        for name in _VAR.findall(template):
            if name not in vars_:
                return None
            value = vars_[name]
            if value not in self.allowed(key, name):
                return None
            text = text.replace("{" + name + "}", str(value))
        return text
