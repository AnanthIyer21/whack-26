"""Leaderboards, kept in SQLite at data/leaderboard.db (data/ is gitignored) (RBadiadka7).

Two boards:
  alltime  the best 10 scores ever on this laptop (party runs, plus solo runs whose player typed a name)
  party    this party's runs; wiped when a party starts and when it ends

A Party (in memory) holds the player order and whose turn it is. 1 round = everyone plays once;
the party board ranks each player's BEST score so far, so "Another round" lets people improve.
"""
import os
import sqlite3
import time

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "leaderboard.db")
TOP_N = 10
MIN_PLAYERS, MAX_PLAYERS = 2, 8
NAME_MAX = 12


def clean_name(name, fallback):
    name = " ".join(str(name).split())[:NAME_MAX]
    return name or fallback


def unique_names(names):
    """Blank names become 'Player N'; duplicates get a number so each player keeps their own row."""
    out = []
    for i, n in enumerate(names):
        base = clean_name(n, f"Player {i + 1}")
        name, k = base, 2
        while name.lower() in (o.lower() for o in out):
            name = f"{base[:NAME_MAX - 2]} {k}"
            k += 1
        out.append(name)
    return out


class Store:
    def __init__(self, path=PATH):
        self.path = path
        self.db = None
        try:
            if path != ":memory:":
                os.makedirs(os.path.dirname(path), exist_ok=True)
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS alltime (id INTEGER PRIMARY KEY, name TEXT, score INTEGER,
                                                    best_combo INTEGER, at REAL);
                CREATE TABLE IF NOT EXISTS party (id INTEGER PRIMARY KEY, name TEXT, score INTEGER,
                                                  best_combo INTEGER, round INTEGER);
                CREATE TABLE IF NOT EXISTS last_names (pos INTEGER PRIMARY KEY, name TEXT);
            """)
            self.db.commit()
        except sqlite3.Error as e:          # a broken database must never stop the game
            print("[leaderboard] disabled:", e)
            self.db = None

    def _run(self, sql, args=(), fetch=False):
        if self.db is None:
            return [] if fetch else None
        try:
            cur = self.db.execute(sql, args)
            if fetch:
                return cur.fetchall()
            self.db.commit()
        except sqlite3.Error as e:
            print("[leaderboard]", e)
            return [] if fetch else None

    # ---- all-time top 10
    def top(self, n=TOP_N):
        return self._run("SELECT name, score FROM alltime ORDER BY score DESC, id ASC LIMIT ?", (n,), fetch=True)

    def qualifies(self, score):
        if score <= 0:
            return False
        rows = self.top()
        return len(rows) < TOP_N or score > rows[-1][1]

    def add_alltime(self, name, score, best_combo=0):
        if score <= 0:
            return
        self._run("INSERT INTO alltime (name, score, best_combo, at) VALUES (?, ?, ?, ?)",
                  (name, int(score), int(best_combo), time.time()))
        self._run("DELETE FROM alltime WHERE id NOT IN "
                  "(SELECT id FROM alltime ORDER BY score DESC, id ASC LIMIT ?)", (TOP_N,))

    # ---- party board
    def party_clear(self):
        self._run("DELETE FROM party")

    def party_add(self, name, score, best_combo, round_):
        self._run("INSERT INTO party (name, score, best_combo, round) VALUES (?, ?, ?, ?)",
                  (name, int(score), int(best_combo), int(round_)))

    def party_best(self):
        """{name: best score} for this party."""
        return {n: s for n, s in self._run("SELECT name, MAX(score) FROM party GROUP BY name", fetch=True)}

    # ---- remembered names for the setup screen
    def last_names(self):
        return [n for _, n in self._run("SELECT pos, name FROM last_names ORDER BY pos", fetch=True)]

    def save_names(self, names):
        self._run("DELETE FROM last_names")
        for i, n in enumerate(names):
            self._run("INSERT INTO last_names (pos, name) VALUES (?, ?)", (i, n))


class Party:
    def __init__(self, names, store):
        self.names = unique_names(names)
        self.store = store
        self.turn = 0                 # index into names
        self.round = 1
        store.party_clear()
        store.save_names(self.names)

    @property
    def current(self):
        return self.names[self.turn]

    @property
    def round_done(self):
        return self.turn >= len(self.names)

    def record(self, score, best_combo):
        """The current player's run ended: save it and move the turn on."""
        name = self.current
        self.store.party_add(name, score, best_combo, self.round)
        self.store.add_alltime(name, score, best_combo)
        self.turn += 1

    def standings(self):
        """[(rank, name, best score or None)], best first; players who haven't played yet go last."""
        best = self.store.party_best()
        order = sorted(self.names, key=lambda n: (best.get(n) is None, -(best.get(n) or 0)))
        out, rank, prev = [], 0, object()
        for i, n in enumerate(order):
            s = best.get(n)
            if s != prev:
                rank = i + 1
                prev = s
            out.append((rank, n, s))
        return out

    def next_round(self):
        self.turn = 0
        self.round += 1

    def end(self):
        self.store.party_clear()
