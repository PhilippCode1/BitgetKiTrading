"""
Integration: Kill-Switch / Safety-Latch stoppt marktseitige Submits ohne Exchange-Call.

Benoetigt migrierte DB (CI: `TEST_DATABASE_URL`, siehe `.github/workflows/ci.yml`).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
_SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for _p in (REPO_ROOT, str(LIVE_BROKER_SRC), str(_SHARED_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from live_broker.config import LiveBrokerSettings
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.service import LiveExecutionService
from live_broker.orders.models import OrderCreateRequest
from live_broker.orders.service import LiveBrokerOrderService
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_rest import BitgetRestError

from shared_py.modul_mate_db_gates import assert_execution_allowed
from shared_py.product_policy import ExecutionPolicyViolationError

pytestmark = pytest.mark.integration

_ARM_DETAIL_MARK = "integration_kill_switch_test_arm"
_RELEASE_SOURCE = "integration_kill_switch_test_cleanup"
_SNAPSHOT_TAG = "kill_switch_integration_bootstrap_account"


def _test_dsn() -> str:
    dsn = (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL nicht gesetzt")
    return dsn


def _live_broker_test_env(monkeypatch: pytest.MonkeyPatch, dsn: str) -> None:
    """Erlaubt 'Live'-Pfad gegen die Test-DB ohne vollstaendigen Kommerz-Governance-Stack."""
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", dsn),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("MODUL_MATE_GATE_ENFORCEMENT", "false"),
        ("LIVE_BROKER_REQUIRE_COMMERCIAL_GATES", "false"),
        ("EXECUTION_MODE", "live"),
        ("STRATEGY_EXEC_MODE", "auto"),
        ("SHADOW_TRADE_ENABLE", "false"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("LIVE_TRADE_ENABLE", "true"),
        ("LIVE_ORDER_SUBMISSION_ENABLED", "true"),
        ("LIVE_ALLOWED_SYMBOLS", "BTCUSDT,ETHUSDT"),
        ("LIVE_ALLOWED_MARKET_FAMILIES", "futures,spot,margin"),
        ("LIVE_ALLOWED_PRODUCT_TYPES", "USDT-FUTURES"),
        ("LIVE_BLOCK_SUBMIT_ON_RECONCILE_FAIL", "false"),
        ("LIVE_BLOCK_SUBMIT_ON_RECONCILE_DEGRADED", "false"),
        ("LIVE_REQUIRE_EXCHANGE_HEALTH", "false"),
        ("LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH", "false"),
        ("BITGET_SYMBOL", "ETHUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
        ("BITGET_API_KEY", "k"),
        ("BITGET_API_SECRET", "s"),
        ("BITGET_API_PASSPHRASE", "p"),
        ("RISK_MAX_POSITION_RISK_PCT", "0.5"),
    ):
        monkeypatch.setenv(k, v)


def _arm_safety_latch_in_db(integration_postgres_conn) -> None:
    integration_postgres_conn.execute(
        """
        INSERT INTO live.audit_trails (
            category, action, severity, scope, scope_key, source, details_json
        ) VALUES (
            'safety_latch', 'arm', 'critical', 'service', 'reconcile', 'integration_test',
            %s::jsonb
        )
        """,
        (f'{{"test_marker": "{_ARM_DETAIL_MARK}"}}',),
    )


def _insert_min_account_snapshot(integration_postgres_conn) -> None:
    """Konten-Truth, damit die Risk-Engine nicht ZUERST blockiert (vor Safety-Latch)."""
    integration_postgres_conn.execute(
        """
        INSERT INTO live.exchange_snapshots (symbol, snapshot_type, raw_data)
        VALUES (
            'USDT',
            'account',
            %s::jsonb
        )
        """,
        (
            json.dumps(
                {
                    "_tag": _SNAPSHOT_TAG,
                    "items": [
                        {
                            "marginCoin": "USDT",
                            "equity": "10000",
                            "available": "9500",
                        }
                    ],
                }
            ),
        ),
    )


def _remove_test_snapshots(integration_postgres_conn) -> None:
    integration_postgres_conn.execute(
        "DELETE FROM live.exchange_snapshots WHERE raw_data->>'_tag' = %s",
        (_SNAPSHOT_TAG,),
    )


def _release_safety_latch_in_db(integration_postgres_conn) -> None:
    """Letzter `safety_latch`-Eintrag == release, damit Folgetests nicht blockieren."""
    integration_postgres_conn.execute(
        """
        INSERT INTO live.audit_trails (
            category, action, severity, scope, scope_key, source, details_json
        ) VALUES (
            'safety_latch', 'release', 'info', 'service', 'reconcile', %s, '{}'::jsonb
        )
        """,
        (_RELEASE_SOURCE,),
    )
    integration_postgres_conn.commit()


class _NoNetworkFakeExchange:
    """Kein echter API-Call; Sicherheitspfad: falls doch, Test bricht hart ab."""

    def build_order_preview(self, intent: object) -> dict[str, Any]:
        return {
            "symbol": getattr(intent, "symbol", "BTCUSDT"),
            "leverage": getattr(intent, "leverage", 1),
        }

    def describe(self) -> dict[str, str]:
        return {"exchange": "bitget"}

    def private_api_configured(self) -> tuple[bool, str]:
        return True, "ok"

    def probe_exchange(self) -> dict[str, Any]:
        raise AssertionError(
            "probe_exchange darf mit probe_exchange=False nicht laufen"
        )

    def place_order(self) -> None:
        raise AssertionError(
            "place_order darf in diesem Szenario nicht aufgerufen werden"
        )


def _execution_intent() -> ExecutionIntentRequest:
    return ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id=f"integ-ks-{uuid.uuid4().hex[:8]}",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=2,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "meta_trade_lane": "candidate_for_live",
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 2,
                "recommended_leverage": 2,
            }
        },
    )


@pytest.fixture
def kill_switch_prepared(
    integration_postgres_conn, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    _test_dsn()
    _arm_safety_latch_in_db(integration_postgres_conn)
    _insert_min_account_snapshot(integration_postgres_conn)
    integration_postgres_conn.commit()
    try:
        yield
    finally:
        _remove_test_snapshots(integration_postgres_conn)
        _release_safety_latch_in_db(integration_postgres_conn)


def test_safety_latch_blocks_order_create_before_private_api(
    integration_postgres_conn, kill_switch_prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsn = _test_dsn()
    _live_broker_test_env(monkeypatch, dsn)
    settings = LiveBrokerSettings()
    repo = LiveBrokerRepository(dsn)
    private = MagicMock()
    private.state_snapshot.return_value = {"ok": True}
    private.place_order = MagicMock(
        side_effect=AssertionError("private place_order: Exchange-Call unerwartet")
    )
    private.modify_order = MagicMock(
        side_effect=AssertionError("private modify_order: unerwartet")
    )
    private.cancel_order = MagicMock(
        side_effect=AssertionError("private cancel_order: unerwartet")
    )

    svc = LiveBrokerOrderService(settings, repo, private, bus=None)

    with pytest.raises(BitgetRestError) as exc:
        svc.create_order(
            OrderCreateRequest(
                source_service="signal-engine",
                symbol="BTCUSDT",
                side="buy",
                size="0.001",
                price="50000",
            )
        )
    err = exc.value
    assert err.classification == "kill_switch"
    assert "Safety latch aktiv" in (err.message or "")
    private.place_order.assert_not_called()


def test_safety_latch_blocks_live_intent(
    integration_postgres_conn, kill_switch_prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsn = _test_dsn()
    _live_broker_test_env(monkeypatch, dsn)
    settings = LiveBrokerSettings()
    ex = _NoNetworkFakeExchange()
    repo = LiveBrokerRepository(dsn)
    svc = LiveExecutionService(settings, ex, repo)  # type: ignore[arg-type]
    out = svc.evaluate_intent(_execution_intent(), probe_exchange=False)
    assert out.get("decision_action") == "blocked"
    assert out.get("decision_reason") == "live_safety_latch_active"


def test_db_tenant_gates_reject_demo_when_account_paused(
    integration_postgres_conn,
) -> None:
    """DB-seitig `account_paused=true` entspricht hartem Stopp (kein Handel, kein 'live true')."""
    row: dict[str, Any] | None = None
    prev_paused = False
    prev_factory = integration_postgres_conn.row_factory
    try:
        integration_postgres_conn.row_factory = dict_row
        row = integration_postgres_conn.execute(
            """
            SELECT account_paused
            FROM app.tenant_modul_mate_gates
            WHERE tenant_id = 'default'
            """
        ).fetchone()
        if row is None:
            pytest.skip(
                "app.tenant_modul_mate_gates fuer 'default' fehlt (Migration 604)"
            )
        prev_paused = bool(row["account_paused"])
        integration_postgres_conn.execute(
            """
            UPDATE app.tenant_modul_mate_gates
            SET account_paused = true
            WHERE tenant_id = 'default'
            """
        )
        with pytest.raises(ExecutionPolicyViolationError) as exc:
            assert_execution_allowed(
                integration_postgres_conn, tenant_id="default", mode="DEMO"
            )
        assert exc.value.reason == "demo_trading_not_permitted"
    finally:
        if row is not None:
            integration_postgres_conn.execute(
                """
                UPDATE app.tenant_modul_mate_gates
                SET account_paused = %s
                WHERE tenant_id = 'default'
                """,
                (prev_paused,),
            )
        integration_postgres_conn.commit()
        integration_postgres_conn.row_factory = prev_factory
