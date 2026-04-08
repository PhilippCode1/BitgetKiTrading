#!/usr/bin/env python3
"""
Validiert shared/prompts/eval_baseline.json (Struktur, Pflichtfelder, release_gate).

Exit 0 bei gueltiger Datei — fuer CI / pre-commit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    p = root / "shared" / "prompts" / "eval_baseline.json"
    if not p.is_file():
        print("FAIL: eval_baseline.json fehlt", file=sys.stderr)
        return 2
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: JSON: {exc}", file=sys.stderr)
        return 2
    bid = str(data.get("baseline_id") or "").strip()
    if not bid:
        print("FAIL: baseline_id fehlt", file=sys.stderr)
        return 2
    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) < 1:
        print("FAIL: cases muss nicht-leeres Array sein", file=sys.stderr)
        return 2
    ids: set[str] = set()
    for i, c in enumerate(cases):
        if not isinstance(c, dict):
            print(f"FAIL: cases[{i}] kein Objekt", file=sys.stderr)
            return 2
        cid = str(c.get("id") or "").strip()
        if not cid:
            print(f"FAIL: cases[{i}].id fehlt", file=sys.stderr)
            return 2
        if cid in ids:
            print(f"FAIL: doppelte case id {cid}", file=sys.stderr)
            return 2
        ids.add(cid)
        if not str(c.get("description_de") or "").strip():
            print(f"FAIL: cases[{cid}].description_de fehlt", file=sys.stderr)
            return 2
        if not str(c.get("category") or "").strip():
            print(f"FAIL: cases[{cid}].category fehlt", file=sys.stderr)
            return 2
        tt = c.get("task_types")
        if tt is not None and not isinstance(tt, list):
            print(f"FAIL: cases[{cid}].task_types muss Liste sein", file=sys.stderr)
            return 2
    if "release_gate" not in data:
        print("FAIL: release_gate fehlt (bool)", file=sys.stderr)
        return 2
    print(f"OK eval_baseline baseline_id={bid} cases={len(ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
