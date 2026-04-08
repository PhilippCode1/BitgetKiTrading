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

from api_gateway.db_dashboard_queries import (
    fetch_signal_by_id,
    fetch_signal_explain,
    fetch_signals_recent,
)
from api_gateway.signal_contract import SIGNAL_API_CONTRACT_VERSION


class _FakeCursor:
    def __init__(self, *, one: dict[str, object] | None = None, many: list[dict[str, object]] | None = None):
        self._one = one
        self._many = many or []

    def fetchone(self) -> dict[str, object] | None:
        return self._one

    def fetchall(self) -> list[dict[str, object]]:
        return self._many


class _FakeConn:
    def __init__(
        self,
        *,
        signal_row: dict[str, object] | None = None,
        recent_rows: list[dict[str, object]] | None = None,
        execution_row: dict[str, object] | None = None,
        alert_row: dict[str, object] | None = None,
        explain_row: dict[str, object] | None = None,
    ):
        self._signal_row = signal_row
        self._recent_rows = recent_rows or []
        self._execution_row = execution_row
        self._alert_row = alert_row
        self._explain_row = explain_row

    def execute(self, sql: str, _params: object) -> _FakeCursor:
        if "FROM app.signals_v1 s" in sql and "LIMIT %(lim)s" in sql:
            return _FakeCursor(many=self._recent_rows)
        if "LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id" in sql:
            return _FakeCursor(one=self._explain_row)
        if "FROM app.signals_v1 s" in sql and "WHERE s.signal_id = %s" in sql:
            return _FakeCursor(one=self._signal_row)
        if "FROM live.execution_decisions d" in sql:
            return _FakeCursor(one=self._execution_row)
        if "FROM alert.alert_outbox o" in sql:
            return _FakeCursor(one=self._alert_row)
        return _FakeCursor()


def test_fetch_signals_recent_includes_hybrid_fields() -> None:
    row = {
        "signal_id": "00000000-0000-0000-0000-000000000001",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "market_regime": "trend",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.82,
        "signal_strength_0_100": 74.0,
        "probability_0_1": 0.72,
        "take_trade_prob": 0.78,
        "take_trade_model_version": "hgb-cal-1700000000000",
        "take_trade_model_run_id": "00000000-0000-4000-8000-0000000000aa",
        "take_trade_calibration_method": "sigmoid",
        "expected_return_bps": 16.0,
        "expected_mae_bps": 22.0,
        "expected_mfe_bps": 34.0,
        "model_uncertainty_0_1": 0.18,
        "uncertainty_effective_for_leverage_0_1": 0.2,
        "model_ood_alert": False,
        "trade_action": "allow_trade",
        "meta_decision_action": "lane_keep",
        "meta_decision_kernel_version": "mkv-1",
        "decision_confidence_0_1": 0.81,
        "decision_policy_version": "hybrid-v2",
        "allowed_leverage": 13,
        "recommended_leverage": 10,
        "leverage_policy_version": "int-leverage-v1",
        "leverage_cap_reasons_json": ["model_cap_binding", "edge_factor_cap"],
        "signal_class": "gross",
        "decision_state": "accepted",
        "analysis_ts_ms": 1_700_000_000_000,
        "created_at": None,
        "wins": 3,
        "losses": 1,
        "evaluations_count": 4,
        "meta_trade_lane": "paper_default",
        "canonical_instrument_id": "bitget:usdt_futures:linear:BTCUSDT",
        "market_family": "usdt_futures",
        "instrument_metadata_snapshot_id": "snap-1",
        "instrument_metadata_raw": {
            "metadata_source": "/api/v2/mix/market/contracts",
            "metadata_verified": True,
            "product_type": "USDT-FUTURES",
            "margin_account_mode": "crossed",
            "quote_coin": "USDT",
            "settle_coin": "USDT",
            "supports_funding": True,
            "supports_open_interest": True,
            "supports_long_short": True,
            "supports_reduce_only": True,
            "supports_leverage": True,
        },
        "rg_live_blocks_raw": [],
        "rg_universal_blocks_raw": [],
        "latest_execution_id": "00000000-0000-0000-0000-000000000099",
        "latest_execution_decision_action": "live_candidate_recorded",
        "latest_execution_decision_reason": "candidate_ready",
        "latest_execution_runtime_mode": "live",
        "latest_execution_requested_mode": "live",
        "latest_execution_created_ts": None,
        "latest_execution_payload": {
            "live_mirror_eligible": True,
            "shadow_live_divergence": {
                "match_ok": False,
                "hard_violations": ["shadow_gap"],
                "soft_violations": [],
            },
        },
        "operator_release_exists": True,
        "operator_release_source": "telegram_operator",
        "operator_release_ts": None,
        "telegram_alert_type": "OPERATOR_PLAN_SUMMARY",
        "telegram_delivery_state": "sent",
        "telegram_message_id": 777,
        "telegram_sent_ts": None,
    }
    items = fetch_signals_recent(
        _FakeConn(recent_rows=[row]),
        symbol=None,
        timeframe=None,
        direction=None,
        min_strength=None,
        market_family=None,
        playbook_id=None,
        playbook_family=None,
        trade_action=None,
        meta_trade_lane=None,
        regime_state=None,
        specialist_router_id=None,
        exit_family=None,
        decision_state=None,
        strategy_name=None,
        signal_class=None,
        signal_registry_key=None,
        limit=10,
    )
    assert items[0]["trade_action"] == "allow_trade"
    assert items[0]["decision_confidence_0_1"] == 0.81
    assert items[0]["allowed_leverage"] == 13
    assert items[0]["recommended_leverage"] == 10
    assert items[0]["uncertainty_effective_for_leverage_0_1"] == 0.2
    assert items[0]["market_family"] == "usdt_futures"
    assert items[0]["meta_trade_lane"] == "paper_default"
    assert items[0]["instrument_metadata_verified"] is True
    assert items[0]["instrument_product_type"] == "USDT-FUTURES"
    assert items[0]["latest_execution_decision_action"] == "live_candidate_recorded"
    assert items[0]["live_mirror_eligible"] is True
    assert items[0]["shadow_live_match_ok"] is False
    assert items[0]["telegram_delivery_state"] == "sent"
    assert items[0]["telegram_alert_type"] == "OPERATOR_PLAN_SUMMARY"
    assert items[0]["signal_contract_version"] == SIGNAL_API_CONTRACT_VERSION
    sv = items[0]["signal_view"]
    assert sv["contract_version"] == SIGNAL_API_CONTRACT_VERSION
    assert sv["identity"]["signal_id"] == "00000000-0000-0000-0000-000000000001"
    assert sv["decision_and_status"]["meta_decision_action"] == "lane_keep"


def test_fetch_signal_by_id_includes_hybrid_fields() -> None:
    row = {
        "signal_id": "00000000-0000-0000-0000-000000000001",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "market_regime": "trend",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.82,
        "regime_reasons_json": [],
        "signal_strength_0_100": 74.0,
        "probability_0_1": 0.72,
        "take_trade_prob": 0.78,
        "take_trade_model_version": "hgb-cal-1700000000000",
        "take_trade_model_run_id": "00000000-0000-4000-8000-0000000000aa",
        "take_trade_calibration_method": "sigmoid",
        "expected_return_bps": 16.0,
        "expected_mae_bps": 22.0,
        "expected_mfe_bps": 34.0,
        "target_projection_models_json": [],
        "model_uncertainty_0_1": 0.18,
        "shadow_divergence_0_1": 0.04,
        "model_ood_score_0_1": 0.0,
        "model_ood_alert": False,
        "uncertainty_reasons_json": [],
        "ood_reasons_json": [],
        "abstention_reasons_json": [],
        "trade_action": "allow_trade",
        "meta_decision_action": "lane_keep",
        "meta_decision_kernel_version": "mkv-2",
        "decision_confidence_0_1": 0.81,
        "decision_policy_version": "hybrid-v2",
        "allowed_leverage": 13,
        "recommended_leverage": 10,
        "leverage_policy_version": "int-leverage-v1",
        "leverage_cap_reasons_json": ["model_cap_binding", "edge_factor_cap"],
        "signal_class": "gross",
        "decision_state": "accepted",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "analysis_ts_ms": 1_700_000_000_000,
        "reasons_json": {"decision_control_flow": {"phase": "x"}},
        "canonical_instrument_id": "bitget:usdt_futures:linear:BTCUSDT",
        "market_family": "usdt_futures",
        "meta_trade_lane": "paper_default",
        "playbook_id": "pb_test",
        "playbook_family": "trend",
        "playbook_decision_mode": "selected",
        "strategy_name": "s1",
        "regime_state": "trend",
        "regime_substate": "trend_x",
        "regime_transition_state": "stable",
        "source_snapshot_json": {
            "instrument_metadata_snapshot_id": "snap-2",
            "instrument_metadata": {
                "snapshot_id": "snap-2",
                "health_status": "ok",
                "entry": {
                    "venue": "bitget",
                    "market_family": "futures",
                    "symbol": "BTCUSDT",
                    "canonical_instrument_id": "bitget:futures:USDT-FUTURES:BTCUSDT",
                    "category_key": "bitget:futures:USDT-FUTURES",
                    "metadata_source": "/api/v2/mix/market/contracts",
                    "metadata_verified": True,
                    "product_type": "USDT-FUTURES",
                    "margin_account_mode": "crossed",
                    "base_coin": "BTC",
                    "quote_coin": "USDT",
                    "settle_coin": "USDT",
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
            },
        },
        "created_at": None,
        "wins": 3,
        "losses": 1,
        "evaluations_count": 4,
    }
    execution_row = {
        "latest_execution_id": "00000000-0000-0000-0000-000000000099",
        "latest_execution_decision_action": "live_candidate_recorded",
        "latest_execution_decision_reason": "candidate_ready",
        "latest_execution_runtime_mode": "live",
        "latest_execution_requested_mode": "live",
        "latest_execution_created_ts": None,
        "latest_execution_payload": {
            "live_mirror_eligible": True,
            "shadow_live_divergence": {
                "match_ok": True,
                "hard_violations": [],
                "soft_violations": ["timing_gap"],
            },
        },
        "operator_release_exists": True,
        "operator_release_source": "telegram_operator",
        "operator_release_ts": None,
    }
    alert_row = {
        "telegram_alert_type": "OPERATOR_PLAN_SUMMARY",
        "telegram_delivery_state": "sent",
        "telegram_message_id": 999,
        "telegram_sent_ts": None,
    }
    item = fetch_signal_by_id(
        _FakeConn(signal_row=row, execution_row=execution_row, alert_row=alert_row),
        UUID("00000000-0000-0000-0000-000000000001"),
    )
    assert item is not None
    assert item["trade_action"] == "allow_trade"
    assert item["decision_confidence_0_1"] == 0.81
    assert item["allowed_leverage"] == 13
    assert item["recommended_leverage"] == 10
    assert item["market_family"] == "usdt_futures"
    assert item["playbook_id"] == "pb_test"
    assert item["meta_trade_lane"] == "paper_default"
    assert item["instrument_metadata"] is not None
    assert item["instrument_venue"] == "bitget"
    assert item["instrument_metadata_verified"] is True
    assert item["instrument_supports_shorting"] is True
    assert item["latest_execution_decision_action"] == "live_candidate_recorded"
    assert item["operator_release_exists"] is True
    assert item["live_mirror_eligible"] is True
    assert item["telegram_alert_type"] == "OPERATOR_PLAN_SUMMARY"
    assert item["meta_decision_action"] == "lane_keep"
    assert item["meta_decision_kernel_version"] == "mkv-2"
    assert item["signal_contract_version"] == SIGNAL_API_CONTRACT_VERSION
    assert item["signal_view"]["deterministic_engine"]["reasons_json_ref"] == "reasons_json"
    assert item["signal_view"]["identity"]["signal_id"] == "00000000-0000-0000-0000-000000000001"


def test_fetch_signal_explain_includes_layers() -> None:
    explain_row = {
        "signal_id": "00000000-0000-0000-0000-0000000000ab",
        "explain_short": "Kurztext",
        "explain_long_md": "## Detail",
        "risk_warnings_json": [{"code": "x"}],
        "stop_explain_json": {"k": "v"},
        "targets_explain_json": {"t": 1},
        "reasons_json": {"engine": True},
    }
    out = fetch_signal_explain(
        _FakeConn(explain_row=explain_row),
        UUID("00000000-0000-0000-0000-0000000000ab"),
    )
    assert out is not None
    assert out["signal_contract_version"] == SIGNAL_API_CONTRACT_VERSION
    assert out["explanation_layers"]["persisted_narrative"]["explain_short"] == "Kurztext"
    assert out["explanation_layers"]["deterministic_engine"]["reasons_json"] == {"engine": True}
    assert out["reasons_json"] == {"engine": True}
    assert out["explanation_layers"]["live_llm_advisory"]["separate_request"] is True
