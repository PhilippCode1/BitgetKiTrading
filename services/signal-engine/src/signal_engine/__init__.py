from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"


def _ensure_monorepo_shared_path() -> None:
    shared_src = Path(__file__).resolve().parents[4] / "shared" / "python" / "src"
    s = str(shared_src)
    if shared_src.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


_ensure_monorepo_shared_path()
