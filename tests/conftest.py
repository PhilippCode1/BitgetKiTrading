"""
Gemeinsame pytest-Konfiguration: Repo-Root und Python-Pfade fuer Services.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_rs = str(_ROOT)
if _rs not in sys.path:
    sys.path.insert(0, _rs)

_fixture_py = _ROOT / "tests" / "fixtures"
if _fixture_py.is_dir():
    _fp = str(_fixture_py)
    if _fp not in sys.path:
        sys.path.insert(0, _fp)

_SERVICE_SRC = [
    _ROOT / "services" / name / "src"
    for name in (
        "feature-engine",
        "signal-engine",
        "paper-broker",
        "structure-engine",
        "drawing-engine",
        "learning-engine",
        "api-gateway",
        "news-engine",
        "monitor-engine",
        "market-stream",
        "llm-orchestrator",
        "live-broker",
    )
]

for p in (_ROOT / "shared" / "python" / "src", *_SERVICE_SRC):
    if p.is_dir():
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
