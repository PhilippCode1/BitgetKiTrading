from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from api_gateway.routes_live import _map_envelope_to_sse


def test_map_signal_envelope_to_sse_includes_hybrid_fields() -> None:
    mapped = _map_envelope_to_sse(
        {
            "event_type": "signal_created",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "payload": {
                "signal_id": "sig-1",
                "direction": "long",
                "market_regime": "trend",
                "signal_strength_0_100": 74.0,
                "probability_0_1": 0.72,
                "take_trade_prob": 0.78,
                "expected_return_bps": 16.0,
                "expected_mae_bps": 22.0,
                "expected_mfe_bps": 34.0,
                "model_uncertainty_0_1": 0.18,
                "model_ood_alert": False,
                "trade_action": "allow_trade",
                "decision_confidence_0_1": 0.81,
                "decision_policy_version": "hybrid-v2",
                "allowed_leverage": 13,
                "recommended_leverage": 10,
                "leverage_policy_version": "int-leverage-v1",
                "leverage_cap_reasons_json": ["model_cap_binding", "edge_factor_cap"],
                "signal_class": "gross",
            },
        },
        symbol="BTCUSDT",
        timeframe="5m",
    )
    assert mapped is not None
    event_name, raw = mapped
    payload = json.loads(raw)
    assert event_name == "signal"
    assert payload["trade_action"] == "allow_trade"
    assert payload["decision_confidence_0_1"] == 0.81
    assert payload["allowed_leverage"] == 13
    assert payload["recommended_leverage"] == 10


def test_map_trade_opened_envelope_to_sse_paper_event() -> None:
    mapped = _map_envelope_to_sse(
        {
            "event_type": "trade_opened",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "payload": {"position_id": "p1", "qty_base": "0.01"},
        },
        symbol="BTCUSDT",
        timeframe="1m",
    )
    assert mapped is not None
    ev, raw = mapped
    assert ev == "paper"
    payload = json.loads(raw)
    assert payload["event_type"] == "trade_opened"
    assert payload["payload"]["position_id"] == "p1"
