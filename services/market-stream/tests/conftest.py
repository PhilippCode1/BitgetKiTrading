"""Erweitert sys.path fuer market_stream, shared_py und config."""

from __future__ import annotations

import sys
from pathlib import Path

_test_dir = Path(__file__).resolve().parent
_market_stream_root = _test_dir.parent
# market-stream/ -> services/ -> repo/
_repo_root = _market_stream_root.parent.parent

for p in (
    str(_market_stream_root / "src"),
    str(_repo_root / "shared" / "python" / "src"),
    str(_repo_root),
):
    if p not in sys.path:
        sys.path.insert(0, p)
