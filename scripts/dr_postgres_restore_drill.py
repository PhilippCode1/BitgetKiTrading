#!/usr/bin/env python3
"""Wrapper: führt tools/dr_postgres_restore_drill.py mit derselben argv aus."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TO = ROOT / "tools" / "dr_postgres_restore_drill.py"
if __name__ == "__main__":
    p = [sys.executable, str(TO), *sys.argv[1:]]
    raise SystemExit(subprocess.call(p, env=os.environ.copy(), cwd=ROOT))  # noqa: S603
