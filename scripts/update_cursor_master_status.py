#!/usr/bin/env python3
"""Alias-Entrypoint fuer den maschinellen CURSOR_MASTER_STATUS-Refresh."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for import_path in (ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from cursor_master_status import main


if __name__ == "__main__":
    raise SystemExit(main())
