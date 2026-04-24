"""
Gemeinsame pytest-Konfiguration: Repo-Root und Python-Pfade fuer Services.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def pytest_configure(config) -> None:  # noqa: ARG001
    # Ohne lokale .env: gleiche Default-Symbole wie in PAPER/Bitget-Contract-Tests, damit
    # Import- und Sammelphase nicht von manuell gesetzten PAPER_DEFAULT_SYMBOL / BITGET_SYMBOL
    # abhängt (FINAL_READINESS: stabile pytest-Läufe in CI und frischen CLIs).
    os.environ.setdefault("PAPER_DEFAULT_SYMBOL", "BTCUSDT")
    os.environ.setdefault("BITGET_SYMBOL", "BTCUSDT")


@pytest.fixture(autouse=True)
def _isolate_host_live_trade_flag_for_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Host-Shell mit LIVE_TRADE_ENABLE=true würde BaseServiceSettings mit EXECUTION_MODE=paper/shadow
    # invalidieren, bevor Test-Setups greifen. Explizit LIVE setzende Tests überschreiben weiter.
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")

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
        "audit-ledger",
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
