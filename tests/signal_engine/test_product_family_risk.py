from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVICE_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (SERVICE_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from signal_engine.hybrid_decision import assess_hybrid_decision
from signal_engine.risk_governor import RISK_GOVERNOR_VERSION, assess_risk_governor
from tests.signal_engine.test_hybrid_decision import _signal_row


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    from signal_engine.config import SignalEngineSettings

    return SignalEngineSettings()


def test_spot_ethusdt_1x_not_futures_leverage_minimum(signal_settings) -> None:
    base_snap = _signal_row()["source_snapshot_json"]
    assert isinstance(base_snap, dict)
    spot = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            signal_class="gross",
            take_trade_prob=0.81,
            expected_return_bps=18.0,
            expected_mae_bps=20.0,
            expected_mfe_bps=34.0,
            model_uncertainty_0_1=0.14,
            market_family="spot",
            source_snapshot_json={
                **base_snap,
                "instrument": {
                    "market_family": "spot",
                    "symbol": "ETHUSDT",
                    "supports_leverage": False,
                },
            },
        ),
    )
    assert spot["market_family"] == "spot"
    assert spot["trade_action"] == "allow_trade"
    assert spot["allowed_leverage"] == 1
    assert spot["recommended_leverage"] == 1
    rg = (spot.get("hybrid_decision") or {}).get("risk_governor") or {}
    assert rg.get("version") == RISK_GOVERNOR_VERSION
    assert int(rg.get("max_leverage_cap") or 0) == 1
    assert "hybrid_allowed_leverage_below_minimum" not in spot["abstention_reasons_json"]


def test_futures_parallel_ethusdt_uses_7x_governor_floor(signal_settings) -> None:
    base_snap = _signal_row()["source_snapshot_json"]
    assert isinstance(base_snap, dict)
    fut = assess_hybrid_decision(
        settings=signal_settings,
        signal_row=_signal_row(
            signal_class="gross",
            take_trade_prob=0.81,
            expected_return_bps=18.0,
            expected_mae_bps=20.0,
            expected_mfe_bps=34.0,
            model_uncertainty_0_1=0.14,
            market_family="futures",
            source_snapshot_json={
                **base_snap,
                "instrument": {
                    "market_family": "futures",
                    "symbol": "ETHUSDT",
                    "product_type": "USDT-FUTURES",
                    "supports_leverage": True,
                    "leverage_max": 75,
                },
            },
        ),
    )
    assert fut["market_family"] == "futures"
    assert fut["trade_action"] == "allow_trade"
    assert fut["allowed_leverage"] >= 7
    assert fut["recommended_leverage"] is not None and int(fut["recommended_leverage"]) >= 7
    rg = (fut.get("hybrid_decision") or {}).get("risk_governor") or {}
    assert int(rg.get("max_leverage_cap") or 0) >= 7


def test_margin_maintenance_margin_rate_halt(signal_settings) -> None:
    gov = assess_risk_governor(
        settings=signal_settings,
        signal_row={
            "direction": "long",
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_confidence_0_1": 0.7,
            "source_snapshot_json": {
                "feature_snapshot": {"primary_tf": {"spread_bps": 1.0, "depth_to_bar_volume_ratio": 1.0}},
                "instrument": {
                    "market_family": "margin",
                    "symbol": "ETHUSDT",
                    "maintenance_margin_rate_0_1": 0.5,
                },
            },
        },
        direction="long",
    )
    assert gov["maintenance_margin_signoff"] == "halt"
    assert "risk_governor_margin_maintenance_margin_rate_too_high" in (
        gov.get("universal_hard_block_reasons_json") or []
    )
