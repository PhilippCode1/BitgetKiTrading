from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "live-broker" / "src" / "live_broker" / "orders" / "service.py"


def test_market_order_requires_slippage_gate_contract() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    assert "market_order_requires_liquidity_slippage_gate" in text
    assert "enable_pre_flight_liquidity_guard" in text
