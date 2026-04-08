from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from api_gateway.db_live_broker_queries import (
    bitget_private_status_from_reconcile_details,
    compute_operator_live_submission_summary,
    fetch_live_broker_runtime,
)


class _FakeCursor:
    def __init__(self, *, one: dict[str, object] | None = None, many: list[dict[str, object]] | None = None):
        self._one = one
        self._many = many or []

    def fetchone(self) -> dict[str, object] | None:
        return self._one

    def fetchall(self) -> list[dict[str, object]]:
        return self._many


class _FakeConn:
    def execute(self, sql: str, _params: object | None = None) -> _FakeCursor:
        if "FROM live.reconcile_snapshots" in sql:
            return _FakeCursor(
                one={
                    "reconcile_snapshot_id": UUID("00000000-0000-0000-0000-000000000001"),
                    "status": "ok",
                    "runtime_mode": "shadow",
                    "upstream_ok": True,
                    "shadow_enabled": True,
                    "live_submission_enabled": False,
                    "decision_counts_json": {"shadow_recorded": 2},
                    "details_json": {"execution_controls": {"strategy_execution_mode": "manual"}},
                    "created_ts": None,
                }
            )
        if "FROM live.orders" in sql and "GROUP BY status" in sql:
            return _FakeCursor(many=[{"status": "new", "total": 1}])
        if "live.kill_switch_events" in sql:
            return _FakeCursor(many=[])
        if "FROM live.audit_trails" in sql and "safety_latch" in sql:
            return _FakeCursor(one=None)
        if "FROM app.instrument_catalog_snapshots" in sql:
            return _FakeCursor(
                one={
                    "snapshot_id": UUID("00000000-0000-0000-0000-000000000002"),
                    "status": "ok",
                    "refreshed_families_json": ["futures"],
                    "counts_json": {"futures": 1},
                    "capability_matrix_json": [],
                    "warnings_json": [],
                    "errors_json": [],
                    "fetch_completed_ts_ms": 2,
                }
            )
        if "FROM live.execution_decisions" in sql:
            return _FakeCursor(
                one={
                    "payload_json": {
                        "instrument_metadata": {
                            "snapshot_id": "snap-7",
                            "health_status": "ok",
                            "session_state": {"trade_allowed_now": True},
                            "entry": {
                                "venue": "bitget",
                                "market_family": "futures",
                                "symbol": "BTCUSDT",
                                "canonical_instrument_id": "bitget:futures:USDT-FUTURES:BTCUSDT",
                                "category_key": "bitget:futures:USDT-FUTURES",
                                "product_type": "USDT-FUTURES",
                                "margin_account_mode": "isolated",
                                "metadata_source": "/api/v2/mix/market/contracts",
                                "metadata_verified": True,
                                "inventory_visible": True,
                                "analytics_eligible": True,
                                "paper_shadow_eligible": True,
                                "live_execution_enabled": True,
                                "execution_disabled": False,
                                "supports_funding": True,
                                "supports_open_interest": True,
                                "supports_long_short": True,
                                "supports_shorting": True,
                                "supports_reduce_only": True,
                                "supports_leverage": True,
                                "public_ws_inst_type": "USDT-FUTURES",
                            },
                        }
                    },
                    "trace_json": {},
                }
            )
        return _FakeCursor(one=None, many=[])


def test_fetch_live_broker_runtime_flattens_nested_instrument_metadata() -> None:
    item = fetch_live_broker_runtime(_FakeConn())
    assert item is not None
    ols = item.get("operator_live_submission")
    assert isinstance(ols, dict)
    assert ols.get("lane") == "live_lane_disabled_config"
    assert isinstance(ols.get("reasons_de"), list)
    assert item["instrument_catalog"]["status"] == "ok"
    assert item["current_instrument_metadata"]["metadata_source"] == "/api/v2/mix/market/contracts"
    assert item["current_instrument_metadata"]["supports_shorting"] is True
    assert item["current_instrument_metadata"]["snapshot_id"] == "snap-7"
    assert item["current_instrument_metadata"]["session_state"]["trade_allowed_now"] is True
    assert item.get("bitget_private_status", {}).get("ui_status") == "unknown"


def test_compute_operator_live_submission_kill_switch_over_config() -> None:
    """Safety schlaegt Konfiguration — konkrete Kill-Switch-Zeilen."""
    out = compute_operator_live_submission_summary(
        reconcile_status="ok",
        upstream_ok=True,
        execution_mode="live",
        live_trade_enable=False,
        live_submission_enabled=False,
        safety_latch_active=False,
        active_kill_switches=[
            {"scope": "global", "scope_key": "*", "reason": "ops_drill", "source": "test"}
        ],
        bitget_private_status={"ui_status": "unknown"},
        require_shadow_match_before_live=False,
    )
    assert out["lane"] == "live_lane_blocked_safety"
    assert out["safety_kill_switch_count"] == 1
    assert any("ops_drill" in x for x in out["reasons_de"])


def test_bitget_private_status_credentials_invalid() -> None:
    st = bitget_private_status_from_reconcile_details(
        {
            "exchange_probe": {
                "demo_mode": True,
                "public_api_ok": True,
                "private_api_configured": True,
                "private_auth_ok": False,
                "private_auth_detail_de": "Signatur",
                "private_auth_classification": "auth",
                "private_auth_exchange_code": "40002",
            }
        }
    )
    assert st["ui_status"] == "credentials_invalid"
    assert st["bitget_connection_label"] == "demo"
    assert st["private_auth_exchange_code"] == "40002"
