#!/usr/bin/env python3
"""gow2-ps4: a log's 10-second performance windows as one table ([frames], [cp], [cores], [cp2] lines).

    perf_timeline.py <gow2_NNN.log> [--summary]

Each row: the time, frames a second, draws a frame, the command processor's share of its core, the same-state draws a
frame, and the busiest cores. --summary adds frame-rate buckets by draws a frame (what a view costs).
"""
import re
import sys
from collections import defaultdict


def main():
    path = sys.argv[1]
    rows = []
    cur = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line[12:20]
        m = re.search(r"\[frames\] ([\d.]+) fps over", line)
        if m:
            cur = {"t": t, "fps": float(m.group(1))}
            rows.append(cur)
            continue
        if not cur:
            continue
        m = re.search(r"\[cp\] 10 s: \d+ swaps \([\d.]+/s\); a frame: (\d+) draws", line)
        if m:
            cur["draws"] = int(m.group(1))
        m = re.search(r"the command processor on the CPU ([\d.]+)", line)
        if m:
            cur["cp"] = float(m.group(1))
        m = re.search(r"(\d+) draws found the state of the draw before them.*?, (\d+) more with fetch", line)
        if m:
            cur["same"] = int(m.group(1)) + int(m.group(2))
        m = re.search(r"\[cores\] core loads ([\d: %]+)", line)
        if m:
            loads = [int(x.split(":")[1]) for x in m.group(1).replace("%", "").split()]
            cur["cores"] = loads
    print(f"{'time':8s} {'fps':>5s} {'draws':>6s} {'cp%':>5s} {'same':>5s}  cores 0-6")
    for r in rows:
        cores = " ".join(f"{c:3d}" for c in r.get("cores", []))
        print(f"{r['t']:8s} {r['fps']:5.1f} {r.get('draws', 0):6d} {r.get('cp', 0):5.1f} {r.get('same', 0):5d}  {cores}")
    if "--summary" in sys.argv:
        buckets = defaultdict(list)
        for r in rows:
            d = r.get("draws", 0)
            if d >= 300:
                buckets[(d // 500) * 500].append(r["fps"])
        print("\ndraws a frame -> fps (10 s windows)")
        for b in sorted(buckets):
            v = buckets[b]
            print(f"  {b:5d}-{b + 499:5d}: {len(v):3d} windows, fps {min(v):5.1f} - {max(v):5.1f}, mean "
                  f"{sum(v) / len(v):5.1f}")


if __name__ == "__main__":
    main()
