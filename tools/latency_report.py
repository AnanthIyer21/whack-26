"""Event-to-voice latency for the pitch slide, from logs/latency.csv.

    python tools/latency_report.py
    python tools/latency_report.py --reset     # start a fresh log (before a measured session)

Groups every spoken line by where it came from and prints p50 / p95 / max.
Targets: bank and pre-fetched lines < 300 ms; live Claude lines < 2.1 s (game over < 3 s).
"""

import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATENCY_CSV = os.path.join(ROOT, "logs", "latency.csv")


def percentile(values, p):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = int(round((p / 100.0) * (len(ordered) - 1)))
    return ordered[index]


def group_of(row):
    spoken = row["spoken_as"]
    if spoken.startswith("prefetch"):
        return "pre-fetched Claude line (pre-voiced)"
    if spoken == "Claude live":
        if row["key"] == "game_over":
            return "live Claude: game over roast"
        return "live Claude: other big moments"
    if spoken == "bank":
        return "bank line"
    return "bank fallback (" + spoken + ")"


def main():
    if "--reset" in sys.argv:
        if os.path.exists(LATENCY_CSV):
            os.remove(LATENCY_CSV)
        print("latency log cleared")
        return
    if not os.path.exists(LATENCY_CSV):
        print("no logs/latency.csv yet: play a few runs with --rival real first")
        return
    groups = {}
    with open(LATENCY_CSV) as f:
        for row in csv.DictReader(f):
            name = group_of(row)
            if name not in groups:
                groups[name] = []
            groups[name].append(float(row["event_to_audio_ms"]))
    print("Event -> GRIP-9000's voice (ms)")
    print("")
    print("source".ljust(46) + "n".rjust(5) + "p50".rjust(8) + "p95".rjust(8) + "max".rjust(8))
    for name in sorted(groups):
        values = groups[name]
        print(name.ljust(46) + str(len(values)).rjust(5) + str(round(percentile(values, 50))).rjust(8)
              + str(round(percentile(values, 95))).rjust(8) + str(round(max(values))).rjust(8))


if __name__ == "__main__":
    main()
