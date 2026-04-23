#!/usr/bin/env python3
"""
Kurzzeit-Simulation hoher Tick-Rate (Memory-Drift-Sanity, kein Ersatz fuer 1h Soak).

Beispiel:
  python tools/tick_stress_memory_probe.py --ticks 200000 --report-every 50000

Optional: ``--tracemalloc`` aktiviert tracemalloc-Snapshots (CPU-Last hoeher).
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import tracemalloc
from dataclasses import dataclass


@dataclass
class Tick:
    sym: str
    px: float
    ts: int


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ticks", type=int, default=50_000)
    p.add_argument("--report-every", type=int, default=10_000)
    p.add_argument("--tracemalloc", action="store_true")
    args = p.parse_args()
    if args.ticks < 1:
        print("ticks must be >= 1", file=sys.stderr)
        return 2
    if args.tracemalloc:
        tracemalloc.start(25)

    gc.collect(2)
    t0 = time.perf_counter()
    peak = 0
    buf: list[Tick] = []
    cap = 10_000
    for i in range(args.ticks):
        buf.append(Tick("BTCUSDT", 42_000.0 + (i % 1000) * 0.01, i))
        if len(buf) > cap:
            buf.clear()
            gc.collect(0)
        if args.report_every and (i + 1) % args.report_every == 0:
            el = time.perf_counter() - t0
            if args.tracemalloc:
                cur, peak = tracemalloc.get_traced_memory()
                print(f"[{i + 1}] elapsed={el:.2f}s tracemalloc_KiB={cur // 1024}/{peak // 1024}")
            else:
                print(f"[{i + 1}] elapsed={el:.2f}s")
    print("done ticks=", args.ticks, "elapsed_s=", round(time.perf_counter() - t0, 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
