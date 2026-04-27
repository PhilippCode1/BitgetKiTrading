from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "live-broker" / "src" / "live_broker" / "orders" / "service.py"
GUARD = ROOT / "services" / "live-broker" / "src" / "live_broker" / "execution" / "liquidity_guard.py"


def test_service_enforces_orderbook_staleness_gate() -> None:
    service_text = SERVICE.read_text(encoding="utf-8")
    guard_text = GUARD.read_text(encoding="utf-8")
    assert "max_orderbook_age_ms" in service_text
    assert "orderbook_stale" in guard_text
