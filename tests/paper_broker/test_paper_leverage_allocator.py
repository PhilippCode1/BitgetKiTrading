from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAPER_SRC = ROOT / "services" / "paper-broker" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (ROOT, PAPER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from paper_broker.config import PaperBrokerSettings
from paper_broker.risk import leverage_allocator as mod


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> PaperBrokerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    # CI-stabile Drawdown-/Margin-Basis, unabhaengig von externer Env.
    monkeypatch.setenv("RISK_MAX_ACCOUNT_DRAWDOWN_PCT", "0.18")
    monkeypatch.setenv("RISK_MAX_ACCOUNT_MARGIN_USAGE", "0.35")
    return PaperBrokerSettings()


def test_allocate_paper_execution_leverage_applies_exchange_and_model_caps(
    settings: PaperBrokerSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "build_auto_plan_bundle",
        lambda *args, **kwargs: (
            {"stop_price": "99500", "quality": {"stop_quality_score": 88}},
            {},
            88,
            "2.0",
        ),
    )
    monkeypatch.setattr(mod, "should_liquidate_approx", lambda **kwargs: False)
    monkeypatch.setattr(
        mod,
        "build_paper_account_risk_metrics",
        lambda *args, **kwargs: {
            "projected_margin_usage_pct": 0.04,
            "account_drawdown_pct": 0.01,
        },
    )

    decision = mod.allocate_paper_execution_leverage(
        None,  # type: ignore[arg-type]
        settings=settings,
        account_row={
            "account_id": "00000000-0000-0000-0000-000000000001",
            "equity": "10000",
            "initial_equity": "10000",
        },
        tenant_id="default",
        contract_max_leverage=20,
        requested_leverage=Decimal("25"),
        signal_payload={"trade_action": "allow_trade", "allowed_leverage": 18},
        symbol="BTCUSDT",
        side="long",
        qty_base=Decimal("0.05"),
        entry_price=Decimal("100000"),
        entry_fee_usdt=Decimal("3"),
        timeframe="5m",
    )
    assert decision["recommended_leverage"] == 18
    assert decision["caps"]["exchange_cap"] == 20
    assert decision["caps"]["model_cap"] == 18


def test_allocate_paper_execution_leverage_blocks_on_drawdown_cap(
    settings: PaperBrokerSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "build_auto_plan_bundle",
        lambda *args, **kwargs: (
            {"stop_price": "99500", "quality": {"stop_quality_score": 88}},
            {},
            88,
            "2.0",
        ),
    )
    monkeypatch.setattr(mod, "should_liquidate_approx", lambda **kwargs: False)
    monkeypatch.setattr(
        mod,
        "build_paper_account_risk_metrics",
        lambda *args, **kwargs: {
            "projected_margin_usage_pct": 0.10,
            "account_drawdown_pct": 0.12,
        },
    )

    decision = mod.allocate_paper_execution_leverage(
        None,  # type: ignore[arg-type]
        settings=settings,
        account_row={
            "account_id": "00000000-0000-0000-0000-000000000001",
            "equity": "8500",
            "initial_equity": "10000",
        },
        tenant_id="default",
        contract_max_leverage=25,
        requested_leverage=Decimal("20"),
        signal_payload={"trade_action": "allow_trade", "allowed_leverage": 18},
        symbol="BTCUSDT",
        side="long",
        qty_base=Decimal("0.05"),
        entry_price=Decimal("100000"),
        entry_fee_usdt=Decimal("3"),
        timeframe="5m",
    )
    # Drawdown-Cap muss deterministisch aus den Settings berechnet und bindend sein.
    expected_drawdown_cap = mod._ratio_cap(
        ratio=0.12,
        hard_limit=float(settings.risk_max_account_drawdown_pct),
        risk_max=25,
    )
    assert decision["allowed_leverage"] == expected_drawdown_cap
    assert decision["recommended_leverage"] == expected_drawdown_cap
    assert "drawdown_cap_binding" in decision["cap_reasons_json"]
