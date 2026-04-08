from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_ME_SRC = _ROOT / "services" / "monitor-engine" / "src"
_SHARED_SRC = _ROOT / "shared" / "python" / "src"
for p in (_ME_SRC, _SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
