from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LE_SRC = REPO / "services" / "learning-engine" / "src"
SHARED_SRC = REPO / "shared" / "python" / "src"
for p in (LE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)
