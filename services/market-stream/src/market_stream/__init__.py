from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"


def _ensure_monorepo_shared_path() -> None:
    # `pip install -e .` inside services/market-stream should still resolve
    # the shared monorepo package without requiring a second manual install step.
    shared_src = Path(__file__).resolve().parents[4] / "shared" / "python" / "src"
    shared_src_str = str(shared_src)
    if shared_src.is_dir() and shared_src_str not in sys.path:
        sys.path.insert(0, shared_src_str)


_ensure_monorepo_shared_path()
