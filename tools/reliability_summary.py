"""Summarise results/reliability.csv into a Markdown table and JSON for the numbers slide.

    python tools/reliability_summary.py                  # all sessions
    python tools/reliability_summary.py --machine NAME   # only trials run on that laptop

Writes results/reliability_table.md and results/reliability.json, and prints the table.
Superseded rows (redone with R) are ignored. Failures stay in: the numbers are honest.
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
CSV_PATH = os.path.join(RESULTS, "reliability.csv")


def pct(passed, n):
    return round(100.0 * passed / n, 1) if n else None


def fmt(p, passed, n):
    return "-" if p is None else f"{p:.0f}% ({passed}/{n})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default=None)
    args = ap.parse_args()
    if not os.path.exists(CSV_PATH):
        print("no results/reliability.csv yet: run tools/reliability_check.py first")
        return
    with open(CSV_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["superseded"] == "0"
                and (args.machine is None or r["machine"] == args.machine)]
    skipped = sum(r["result"] == "SKIP" for r in rows)
    rows = [r for r in rows if r["result"] != "SKIP"]       # retried later; the retry is counted

    cells = defaultdict(lambda: {"GRIP": [0, 0], "OPEN": [0, 0], "rt": []})
    reasons = Counter()
    for r in rows:
        c = cells[(r["person"], r["hand"])]
        c[r["prompt"]][1] += 1
        if r["result"] == "PASS":
            c[r["prompt"]][0] += 1
            if r["reaction_ms"]:
                c["rt"].append(float(r["reaction_ms"]))
        else:
            reasons[r["reason"]] += 1

    lines = ["| Person | Hand | Grip recognised | Open recognised | Overall | Median time to recognise |",
             "|---|---|---|---|---|---|"]
    out = {"rows": [], "fail_reasons": dict(reasons)}
    tot = {"GRIP": [0, 0], "OPEN": [0, 0], "rt": []}
    for (person, hand), c in sorted(cells.items()):
        gp, gn = c["GRIP"]
        op, on = c["OPEN"]
        rt = sorted(c["rt"])
        med = rt[len(rt) // 2] if rt else None
        lines.append(f"| {person} | {hand} | {fmt(pct(gp, gn), gp, gn)} | {fmt(pct(op, on), op, on)} | "
                     f"{fmt(pct(gp + op, gn + on), gp + op, gn + on)} | {'-' if med is None else f'{med:.0f} ms'} |")
        out["rows"].append({"person": person, "hand": hand, "grip_pct": pct(gp, gn), "open_pct": pct(op, on),
                            "overall_pct": pct(gp + op, gn + on), "n": gn + on, "median_reaction_ms": med})
        for k in ("GRIP", "OPEN"):
            tot[k][0] += c[k][0]
            tot[k][1] += c[k][1]
        tot["rt"] += c["rt"]
    gp, gn = tot["GRIP"]
    op, on = tot["OPEN"]
    rt = sorted(tot["rt"])
    med = rt[len(rt) // 2] if rt else None
    lines.append(f"| **All** | | **{fmt(pct(gp, gn), gp, gn)}** | **{fmt(pct(op, on), op, on)}** | "
                 f"**{fmt(pct(gp + op, gn + on), gp + op, gn + on)}** | {'-' if med is None else f'{med:.0f} ms'} |")
    out["overall"] = {"grip_pct": pct(gp, gn), "open_pct": pct(op, on), "overall_pct": pct(gp + op, gn + on),
                      "n": gn + on, "people": len({p for p, _ in cells}), "median_reaction_ms": med}

    note = ("\nA trial passes when the pose is recognised and held for 0.3 s within 2 s of the prompt, with "
            "exactly one hand in frame. Every trial starts from the opposite pose. OPEN must be recognised as "
            "open (unclear doesn't count). Grip and open come from MediaPipe landmarks plus our own "
            "finger-curl maths; nothing is trained.\n")
    if skipped:
        note += f"\n{skipped} trial(s) were retried because the starting pose wasn't reached in 3 s.\n"
    if reasons:
        note += "\nFailures by reason: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()) + "\n"
    table = "\n".join(lines) + "\n" + note
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "reliability_table.md"), "w") as f:
        f.write("# Grip / open reliability\n\n" + table)
    with open(os.path.join(RESULTS, "reliability.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(table)
    print("wrote results/reliability_table.md and results/reliability.json")


if __name__ == "__main__":
    main()
