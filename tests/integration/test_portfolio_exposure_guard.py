"""
Multi-Instrument-Exposure-Guard: 4 grosse DB-Positionen, 5. Eroeffnung muss
PORTFOLIO_EXPOSURE_EXCEEDED auslösen (live-broker risk_adapter + survival_kernel-Buffer).
"""

from __future__ import annotations

import sys
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
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.risk_adapter import PORTFOLIO_EXPOSURE_EXCEEDED
from live_broker.execution.service import LiveExecutionService

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
                                "available": "5000",
                            }
                        ],
                    },
                }
            ],
            "positions": [],
        }
        self.reconcile_snapshot: dict[str, object] = {
            "details_json": {"drift": {"snapshot_health": {"missing_types": [], "stale_types": []}}}
        }

    def record_execution_decision(self, record: dict[str, object]) -> dict[str, object]:
        return {**record, "execution_id": str(uuid4())}

    def record_execution_risk_snapshot(self, _eid: str, _risk: dict[str, object]) -> None:
        return None

    def record_shadow_live_assessment(self, **_: object) -> None:
        return None

    def list_latest_exchange_snapshots(
        self, snapshot_type: str, *, symbol: str | None = None, limit: int = 200
    ) -> list[dict[str, object]]:
        items = list(self.snapshots.get(snapshot_type, []))
        if symbol is not None:
            items = [i for i in items if i.get("symbol") == symbol]
        return items[:limit]

    def list_exchange_snapshots_since(
        self, snapshot_type: str, *, since_ts_ms: int, symbol: str | None = None, limit: int = 5000
    ) -> list[dict[str, object]]:
        return self.list_latest_exchange_snapshots(snapshot_type, symbol=symbol, limit=limit)

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


def test_fifth_order_blocked_portfolio_exposure_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
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
    service = LiveExecutionService(settings, _FakeEx(), repo)  # type: ignore[arg-type]
    # Notional 5. Order: qty*entry*7, z.B. 100 * 0.1 * 7 = 70; Summe 2000+70 > Cap 2000
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
