#!/usr/bin/env python3
"""
Aktualisiert config/schema_master.hash. Bevorzugt: tools/refresh_schema_master_hash.py
(nutzt ggf. DATABASE_URL fuer LIVE_APP_SCHEMA).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_R = _ROOT / "tools" / "refresh_schema_master_hash.py"
_spec = importlib.util.spec_from_file_location("refresh_schema_master_hash", _R)
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise RuntimeError("refresh_schema_master_hash load")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
main = _mod.main


if __name__ == "__main__":
    raise SystemExit(main())
