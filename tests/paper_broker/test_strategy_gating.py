from __future__ import annotations

import pytest
from paper_broker.config import PaperBrokerSettings
from paper_broker.strategy.gating import (
    GateConfig,
    direction_to_side,
    should_auto_trade,
    warnung_against_position,
)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> PaperBrokerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    return PaperBrokerSettings()


def test_should_auto_trade_ok(settings: PaperBrokerSettings) -> None:
    cfg = GateConfig(
        min_strength=settings.strat_min_signal_strength,
        min_prob=float(settings.strat_min_probability),
        min_risk_score=settings.strat_min_risk_score,
        min_expected_return_bps=float(settings.strat_min_expected_return_bps),
        max_expected_mae_bps=float(settings.strat_max_expected_mae_bps),
        min_projected_rr=float(settings.strat_min_projected_rr),
    )
    sig = {
        "decision_state": "accepted",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "signal_strength_0_100": 80,
        "probability_0_1": 0.7,
        "risk_score_0_100": 65,
        "expected_return_bps": 18.0,
        "expected_mae_bps": 22.0,
        "expected_mfe_bps": 36.0,
    }
    ok, reasons = should_auto_trade(sig, cfg)
    assert ok
    assert reasons == []


def test_should_auto_trade_rejected() -> None:
    cfg = GateConfig(min_strength=50, min_prob=0.5, min_risk_score=50)
    ok, reasons = should_auto_trade(
        {
            "decision_state": "rejected",
            "rejection_state": False,
            "signal_strength_0_100": 90,
            "probability_0_1": 0.9,
            "risk_score_0_100": 90,
        },
        cfg,
    )
    assert not ok
    assert "not_accepted" in reasons


def test_warnung_against_position() -> None:
    assert warnung_against_position(
        {"signal_class": "warnung", "direction": "short"},
        "long",
    )
    assert not warnung_against_position(
        {"signal_class": "warnung", "direction": "long"},
        "long",
    )


def test_should_auto_trade_honors_trade_action_do_not_trade() -> None:
    cfg = GateConfig(min_strength=50, min_prob=0.5, min_risk_score=50)
    ok, reasons = should_auto_trade(
        {
            "trade_action": "do_not_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 90,
            "probability_0_1": 0.9,
            "risk_score_0_100": 90,
        },
        cfg,
    )
    assert not ok
    assert "trade_action_do_not_trade" in reasons


def test_should_auto_trade_rejects_bad_projected_profile() -> None:
    cfg = GateConfig(
        min_strength=50,
        min_prob=0.5,
        min_risk_score=50,
        min_expected_return_bps=5.0,
        max_expected_mae_bps=80.0,
        min_projected_rr=1.2,
    )
    ok, reasons = should_auto_trade(
        {
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 90,
            "probability_0_1": 0.9,
            "risk_score_0_100": 90,
            "expected_return_bps": -3.0,
            "expected_mae_bps": 110.0,
            "expected_mfe_bps": 70.0,
        },
        cfg,
    )
    assert not ok
    assert "expected_return_low" in reasons
    assert "expected_mae_high" in reasons
    assert "projected_rr_low" in reasons


def test_direction_to_side() -> None:
    assert direction_to_side("long") == "long"
    assert direction_to_side(" SHORT ") == "short"
    assert direction_to_side("flat") is None


def test_warnung_same_side_not_blocked() -> None:
    assert (
        warnung_against_position(
            {"signal_class": "warnung", "direction": "long"},
            "long",
        )
        is False
    )


def test_warnung_requires_open_side() -> None:
    assert (
        warnung_against_position(
            {"signal_class": "warnung", "direction": "short"},
            None,
        )
        is False
    )


def test_should_auto_trade_blocks_shock_regime() -> None:
    cfg = GateConfig(min_strength=50, min_prob=0.5, min_risk_score=50)
    ok, reasons = should_auto_trade(
        {
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 90,
            "probability_0_1": 0.9,
            "risk_score_0_100": 90,
            "market_regime": "shock",
        },
        cfg,
    )
    assert not ok
    assert "market_regime_shock" in reasons
