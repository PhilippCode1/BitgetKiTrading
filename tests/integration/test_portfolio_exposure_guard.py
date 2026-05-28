"""
Rigorose E2E/Integrationstest-Suite zur Validierung der Hebel-Hard-Caps,
des Preflight-Sicherheitsgatter-Schutzwalls, des Globalen Handelsstopps (halt latch)
und der Volatilitäts-Hebel-Dämpfung (volatility leverage clamp).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings
from live_broker.exceptions import SecurityException
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.risk_adapter import PORTFOLIO_EXPOSURE_EXCEEDED
from live_broker.execution.service import LiveExecutionService
from paper_broker.config import PaperBrokerSettings

pytestmark = pytest.mark.live_mock


def _strong_signal() -> dict[str, object]:
    return {
        "trade_action": "allow_trade",
        "decision_state": "accepted",
        "rejection_state": False,
        "signal_strength_0_100": 90,
        "probability_0_1": 0.8,
        "risk_score_0_100": 80,
        "expected_return_bps": 14.0,
        "expected_mae_bps": 15.0,
        "expected_mfe_bps": 28.0,
        "allowed_leverage": 7,
        "recommended_leverage": 7,
    }


class _FakeEx:
    def build_order_preview(self, intent) -> dict[str, object]:
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self) -> dict[str, object]:
        return {"exchange": "bitget"}

    def private_api_configured(self) -> tuple[bool, str]:
        return True, "ok"


class _Repo:
    def __init__(self, live_positions: list[dict[str, object]]) -> None:
        self._live_positions = live_positions
        self.snapshots: dict[str, list[dict[str, object]]] = {
            "account": [
                {
                    "symbol": "USDT",
                    "raw_data": {
                        "items": [
                            {
                                "marginCoin": "USDT",
                                "equity": "10000",
                                "available": "9500", # Macht used_margin = 500 (5%), weit unter 35% Limit
                            }
                        ],
                    },
                }
            ],
            "positions": [],
        }
        self.reconcile_snapshot: dict[str, object] = {
            "details_json": {
                "drift": {"snapshot_health": {"missing_types": [], "stale_types": []}}
            }
        }

    def record_execution_decision(self, record: dict[str, object]) -> dict[str, object]:
        return {**record, "execution_id": str(uuid4())}

    def record_execution_journal(self, record: dict[str, object]) -> dict[str, object]:
        return record

    def record_execution_risk_snapshot(
        self, _eid: str, _risk: dict[str, object]
    ) -> None:
        return None

    def record_shadow_live_assessment(self, **_: object) -> None:
        return None

    def safety_latch_is_active(self) -> bool:
        return False

    def list_latest_exchange_snapshots(
        self, snapshot_type: str, *, symbol: str | None = None, limit: int = 200
    ) -> list[dict[str, object]]:
        items = list(self.snapshots.get(snapshot_type, []))
        if symbol is not None:
            items = [i for i in items if i.get("symbol") == symbol]
        return items[:limit]

    def list_exchange_snapshots_since(
        self,
        snapshot_type: str,
        *,
        since_ts_ms: int,
        symbol: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, object]]:
        return self.list_latest_exchange_snapshots(
            snapshot_type, symbol=symbol, limit=limit
        )

    def latest_reconcile_snapshot(self) -> dict[str, object] | None:
        return self.reconcile_snapshot

    def fetch_online_drift_state(self) -> object:
        return None

    def list_live_positions(self) -> list[dict[str, object]]:
        return self._live_positions


@pytest.fixture(autouse=True)
def _no_db_m604() -> object:
    with patch.object(
        LiveExecutionService,
        "_assert_db_live_execution_policy",
        lambda _self: None,
    ):
        yield


def test_fifth_order_blocked_portfolio_exposure_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    4 grosse offene (DB-)Positionen, Equity 10k, Basislimit 25 %, mit 5 Instrumenten
    sinkt effektiv auf 20 % (Buffer) => Cap 2000. Bestand 4*500 + neue Order-Notional > 2000.
    """
    symbols_4 = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT")
    positions = [
        {
            "inst_id": s,
            "product_type": "USDT-FUTURES",
            "hold_side": "long",
            "size_base": "0.1",
            "entry_price": "1",
            "notional_value": 500.0,
            "raw_json": {"leverage": 7},
        }
        for s in symbols_4
    ]
    for key, v in {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "shadow",
        "STRATEGY_EXEC_MODE": "auto",
        "SHADOW_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_ALLOWED_SYMBOLS": "BTCUSDT,ETHUSDT,SOLUSDT,ADAUSDT,DOTUSDT",
        "LIVE_ALLOWED_MARKET_FAMILIES": "futures,spot,margin",
        "LIVE_ALLOWED_PRODUCT_TYPES": "USDT-FUTURES",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_DEMO_ENABLED": "false",
        "BITGET_DEMO_API_KEY": "",
        "BITGET_DEMO_API_SECRET": "",
        "BITGET_DEMO_API_PASSPHRASE": "",
        "RISK_MAX_CONCURRENT_POSITIONS": "20",
        "RISK_MAX_PORTFOLIO_EXPOSURE_PCT": "0.25",
        "RISK_PORTFOLIO_DIVERSIFICATION_BUFFER_PER_INSTRUMENT": "0.05",
        "BITGET_SYMBOL": "BTCUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_API_KEY": "k",
        "BITGET_API_SECRET": "s",
        "BITGET_API_PASSPHRASE": "p",
    }.items():
        monkeypatch.setenv(key, v)

    settings = LiveBrokerSettings()
    repo = _Repo(positions)
    # Für Exposure-Limit-Test muss account snapshot passendes and available margin haben
    repo.snapshots["account"][0]["raw_data"]["items"][0]["available"] = "5000"
    service = LiveExecutionService(settings, _FakeEx(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="p38",
        symbol="DOTUSDT",
        direction="long",
        requested_runtime_mode="shadow",
        leverage=7,
        approved_7x=True,
        qty_base="0.1",
        entry_price="100",
        stop_loss="90",
        take_profit="120",
        payload={"signal_payload": _strong_signal()},
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    re = (out.get("payload_json") or {}).get("risk_engine") or {}
    assert re.get("decision_reason") == PORTFOLIO_EXPOSURE_EXCEEDED
    assert "PORTFOLIO_EXPOSURE_EXCEEDED" in (re.get("reasons_json") or [])


def test_adversarial_standard_leverage_injection_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Sollte ein Angreifer versuchen, im Modus STANDARD_FUTURES einen bösartigen Hebel von 15x
    oder 50x einzuschleusen, so muss der Preflight-Check die Order vernichten, einen Sicherheitsalarm
    auslösen und das System in den globalen Handelsstopp (global_halt_latch) überführen.
    """
    for key, v in {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "STRATEGY_EXEC_MODE": "auto",
        "SHADOW_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "true",
        "LIVE_ALLOWED_SYMBOLS": "BTCUSDT",
        "LIVE_ALLOWED_MARKET_FAMILIES": "futures",
        "LIVE_ALLOWED_PRODUCT_TYPES": "USDT-FUTURES",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_DEMO_ENABLED": "false",
        "BITGET_DEMO_API_KEY": "",
        "BITGET_DEMO_API_SECRET": "",
        "BITGET_DEMO_API_PASSPHRASE": "",
        "RISK_MAX_CONCURRENT_POSITIONS": "20",
        "RISK_MAX_PORTFOLIO_EXPOSURE_PCT": "0.25",
        "RISK_PORTFOLIO_DIVERSIFICATION_BUFFER_PER_INSTRUMENT": "0.05",
        "BITGET_SYMBOL": "BTCUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_API_KEY": "k",
        "BITGET_API_SECRET": "s",
        "BITGET_API_PASSPHRASE": "p",
        "BITGET_RELAX_CREDENTIAL_ISOLATION": "true",
        "LIVE_ALLOW_ORDER_SUBMIT": "true",
        "RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE": "75",
    }.items():
        monkeypatch.setenv(key, v)

    settings = LiveBrokerSettings()
    repo = _Repo([])

    halt_called = []
    def mock_publish_global_halt_state(redis_url: str, active: bool) -> None:
        halt_called.append(active)

    # Patch global_halt_latch so we can capture the trigger, und exit_preview um Validierungs-Block zu umgehen
    with patch("live_broker.global_halt_latch.publish_global_halt_state", mock_publish_global_halt_state), \
         patch.object(LiveExecutionService, "_exit_preview", lambda *args, **kwargs: {"valid": True}):
         
        service = LiveExecutionService(settings, _FakeEx(), repo)  # type: ignore[arg-type]
        
        # STANDARD_FUTURES mit Hebel 15x (erlaubtes Maximum ist 11x)
        intent = ExecutionIntentRequest(
            source_service="signal-engine",
            signal_id="p-adv-standard-15x",
            symbol="BTCUSDT",
            direction="long",
            requested_runtime_mode="live",
            leverage=15,
            approved_7x=True,
            qty_base="0.1",
            entry_price="100",
            stop_loss="90",
            take_profit="120",
            payload={"signal_payload": {**_strong_signal(), "execution_mode": "STANDARD_FUTURES", "allowed_leverage": 15, "recommended_leverage": 15}},
        )

        with pytest.raises(SecurityException) as exc_info:
            service.evaluate_intent(intent, probe_exchange=False)

        assert "Preflight leverage cap violation" in str(exc_info.value)
        # Verifiziere, dass global_halt_latch erfolgreich ausgelöst wurde
        assert halt_called == [True]


def test_adversarial_bot_leverage_injection_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Sollte ein Signal im BOT_GRID Modus einen bösartigen Hebel von 25x oder 75x fordern,
    so muss der Preflight-Check dies blockieren, die Übermittlung an die API verhindern und
    die Sicherheitsmetrik security_leverage_violation_attempts_total erhöhen.
    """
    for key, v in {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "STRATEGY_EXEC_MODE": "auto",
        "SHADOW_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "true",
        "LIVE_ALLOWED_SYMBOLS": "BTCUSDT",
        "LIVE_ALLOWED_MARKET_FAMILIES": "futures",
        "LIVE_ALLOWED_PRODUCT_TYPES": "USDT-FUTURES",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_DEMO_ENABLED": "false",
        "BITGET_DEMO_API_KEY": "",
        "BITGET_DEMO_API_SECRET": "",
        "BITGET_DEMO_API_PASSPHRASE": "",
        "RISK_MAX_CONCURRENT_POSITIONS": "20",
        "RISK_MAX_PORTFOLIO_EXPOSURE_PCT": "0.25",
        "RISK_PORTFOLIO_DIVERESIFICATION_BUFFER_PER_INSTRUMENT": "0.05",
        "BITGET_SYMBOL": "BTCUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_API_KEY": "k",
        "BITGET_API_SECRET": "s",
        "BITGET_API_PASSPHRASE": "p",
        "BITGET_RELAX_CREDENTIAL_ISOLATION": "true",
        "LIVE_ALLOW_ORDER_SUBMIT": "true",
        "RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE": "75",
    }.items():
        monkeypatch.setenv(key, v)

    settings = LiveBrokerSettings()
    repo = _Repo([])

    from live_broker.execution import liquidity_guard
    initial_violations = liquidity_guard.leverage_violation_counter

    # Patch exit_preview um Validierungs-Block zu umgehen
    with patch.object(LiveExecutionService, "_exit_preview", lambda *args, **kwargs: {"valid": True}):
        service = LiveExecutionService(settings, _FakeEx(), repo)  # type: ignore[arg-type]

        # BOT_GRID mit Hebel 25x (erlaubtes Maximum ist 22x)
        intent = ExecutionIntentRequest(
            source_service="signal-engine",
            signal_id="p-adv-bot-25x",
            symbol="BTCUSDT",
            direction="long",
            requested_runtime_mode="live",
            leverage=25,
            approved_7x=True,
            qty_base="0.1",
            entry_price="100",
            stop_loss="90",
            take_profit="120",
            payload={"signal_payload": {**_strong_signal(), "execution_mode": "BOT_GRID", "allowed_leverage": 25, "recommended_leverage": 25}},
        )

        with pytest.raises(SecurityException) as exc_info:
            service.evaluate_intent(intent, probe_exchange=False)

        assert "Preflight leverage cap violation" in str(exc_info.value)
        # Verifiziere, dass die Metrik/Counter-Variable erhöht wurde
        assert liquidity_guard.leverage_violation_counter == initial_violations + 1


def test_volatility_leverage_clamp_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Szenario mit extremer Volatilität und hoher VPIN-Toxizität.
    Das System muss den Hebel automatisch weit unter die Hard-Caps zwingen (z. B. auf 2x oder 3x),
    obwohl das Signal theoretisch das Maximum angefordert hat.
    """
    from paper_broker.risk import leverage_allocator as mod

    # CI-stabile Drawdown- und Margin-Limits, unabhängig von externer Env.
    monkeypatch.setenv("RISK_MAX_ACCOUNT_DRAWDOWN_PCT", "0.18")
    monkeypatch.setenv("RISK_MAX_ACCOUNT_MARGIN_USAGE", "0.35")
    
    settings = PaperBrokerSettings()

    # Extreme Volatilität => Großer ATR-basierter Stop-Abstand (z. B. Einstieg 100000, Stop bei 60000)
    monkeypatch.setattr(
        mod,
        "build_auto_plan_bundle",
        lambda *args, **kwargs: (
            {"stop_price": "60000", "quality": {"stop_quality_score": 88}},
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
        contract_max_leverage=75,
        requested_leverage=Decimal("75"),  # Signal fordert den maximalen Hebel
        signal_payload={"trade_action": "allow_trade", "allowed_leverage": 75},
        symbol="BTCUSDT",
        side="long",
        qty_base=Decimal("0.05"),
        entry_price=Decimal("100000"),
        entry_fee_usdt=Decimal("3"),
        timeframe="5m",
    )

    # Verifiziere, dass der Hebel-Allocator den Hebel auf <= 3 gedämpft hat.
    # Da 3x unter dem Mindesthebel von 7x liegt, ist recommended_leverage blockiert (None),
    # aber das berechnete allowed_leverage ist präzise gedämpft auf <= 3x.
    assert decision["recommended_leverage"] is None
    assert decision["allowed_leverage"] <= 3
