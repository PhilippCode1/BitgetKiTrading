from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from live_broker.config import LiveBrokerSettings
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.service import LiveExecutionService

from shared_py.bitget import UnknownInstrumentError
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry, BitgetInstrumentCatalogSnapshot
from shared_py.eventbus import EventEnvelope
from tests.fixtures.family_runtime_matrix import FAMILY_RUNTIME_CASES


class _FakeExchangeClient:
    def build_order_preview(self, intent) -> dict[str, object]:
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self) -> dict[str, object]:
        return {"exchange": "bitget"}

    def private_api_configured(self) -> tuple[bool, str]:
        return True, "ok"


class _FakeRepo:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []
        self.snapshots: dict[str, list[dict[str, object]]] = {
            "account": [],
            "positions": [],
            "orders": [],
        }
        self.reconcile_snapshot: dict[str, object] | None = None
        self.online_drift_state: dict[str, object] | None = None

    def record_execution_decision(self, record: dict[str, object]) -> dict[str, object]:
        out = {**record, "execution_id": str(uuid4())}
        self.records.append(out)
        return out

    def record_execution_risk_snapshot(self, execution_decision_id: str, risk_decision: dict) -> None:
        return None

    def record_shadow_live_assessment(self, **kwargs: object) -> None:
        return None

    def list_latest_exchange_snapshots(
        self,
        snapshot_type: str,
        *,
        symbol: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        items = list(self.snapshots.get(snapshot_type, []))
        if symbol is not None:
            items = [item for item in items if item.get("symbol") == symbol]
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
            snapshot_type,
            symbol=symbol,
            limit=limit,
        )

    def latest_reconcile_snapshot(self) -> dict[str, object] | None:
        return self.reconcile_snapshot

    def fetch_online_drift_state(self) -> dict[str, object] | None:
        return self.online_drift_state


class _FakeCatalog:
    def __init__(self, entries: list[BitgetInstrumentCatalogEntry]) -> None:
        self._snapshot = BitgetInstrumentCatalogSnapshot(
            snapshot_id="snap-1",
            source_service="test",
            refresh_reason="test",
            status="ok",
            fetch_started_ts_ms=1,
            fetch_completed_ts_ms=1,
            refreshed_families=["futures"],
            entries=entries,
        )

    def resolve(self, *, symbol: str, market_family: str | None = None, **_: object):
        for entry in self._snapshot.entries:
            if entry.symbol == symbol and entry.market_family == (market_family or entry.market_family):
                return entry
        raise UnknownInstrumentError(symbol)


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "shadow",
        "STRATEGY_EXEC_MODE": "manual",
        "SHADOW_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_ALLOWED_SYMBOLS": "BTCUSDT,ETHUSDT",
        "LIVE_ALLOWED_MARKET_FAMILIES": "futures,spot,margin",
        "LIVE_ALLOWED_PRODUCT_TYPES": "USDT-FUTURES",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
    }
    values.update(extra)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def test_handle_signal_event_blocks_do_not_trade_and_records_leverage_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    envelope = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "sig-1",
            "direction": "long",
            "trade_action": "do_not_trade",
            "allowed_leverage": 6,
            "recommended_leverage": None,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": ["model_cap_binding"],
        },
    )

    result = service.handle_signal_event(envelope)

    assert result["decision_reason"] == "trade_action_do_not_trade"
    assert result["payload_json"]["signal_allowed_leverage"] == 6
    assert result["payload_json"]["signal_leverage_cap_reasons_json"] == ["model_cap_binding"]
    assert result["payload_json"]["risk_engine"]["decision_reason"] == "trade_action_do_not_trade"


def test_handle_signal_event_uses_signal_recommended_leverage_in_decision_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    envelope = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "sig-2",
            "direction": "long",
            "trade_action": "allow_trade",
            "allowed_leverage": 12,
            "recommended_leverage": 9,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": ["model_cap_binding"],
        },
    )

    result = service.handle_signal_event(envelope)

    assert result["decision_reason"] == "missing_execution_plan"
    assert result["leverage"] == 9
    assert result["payload_json"]["signal_recommended_leverage"] == 9


def test_handle_signal_event_blocks_when_shared_risk_hits_max_positions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    repo.snapshots["account"] = [
        {
            "symbol": "USDT",
            "raw_data": {
                "items": [
                    {
                        "marginCoin": "USDT",
                        "equity": "10000",
                        "available": "9000",
                    }
                ]
            },
        }
    ]
    repo.snapshots["positions"] = [
        {
            "symbol": "BTCUSDT",
            "raw_data": {
                "items": [
                    {
                        "instId": "BTCUSDT",
                        "holdSide": "long",
                        "total": "0.10",
                        "margin": "1000",
                    }
                ]
            },
        }
    ]
    repo.reconcile_snapshot = {
        "details_json": {
            "drift": {
                "snapshot_health": {
                    "missing_types": [],
                    "stale_types": [],
                }
            }
        }
    }
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    envelope = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "sig-3",
            "direction": "long",
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 90,
            "probability_0_1": 0.8,
            "risk_score_0_100": 80,
            "expected_return_bps": 14.0,
            "expected_mae_bps": 15.0,
            "expected_mfe_bps": 28.0,
            "allowed_leverage": 12,
            "recommended_leverage": 9,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": [],
        },
    )

    result = service.handle_signal_event(envelope)

    assert result["decision_reason"] == "max_concurrent_positions_exceeded"
    assert result["payload_json"]["risk_engine"]["decision_reason"] == "max_concurrent_positions_exceeded"


def test_handle_signal_event_blocks_when_live_snapshots_are_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    repo.snapshots["account"] = [
        {
            "symbol": "USDT",
            "raw_data": {"items": [{"marginCoin": "USDT", "equity": "10000"}]},
        }
    ]
    repo.reconcile_snapshot = {
        "details_json": {
            "drift": {
                "snapshot_health": {
                    "missing_types": ["account"],
                    "stale_types": ["positions"],
                }
            }
        }
    }
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    envelope = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "sig-4",
            "direction": "long",
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 90,
            "probability_0_1": 0.8,
            "risk_score_0_100": 80,
            "expected_return_bps": 14.0,
            "expected_mae_bps": 15.0,
            "expected_mfe_bps": 28.0,
            "allowed_leverage": 12,
            "recommended_leverage": 9,
            "leverage_policy_version": "int-leverage-v1",
            "leverage_cap_reasons_json": [],
        },
    )

    result = service.handle_signal_event(envelope)

    assert result["decision_reason"] == "live_snapshot_account_missing"
    assert "live_snapshot_positions_stale" in result["payload_json"]["risk_engine"]["reasons_json"]


def test_handle_signal_event_blocks_when_exit_preview_conflicts_with_leverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    repo.snapshots["account"] = [
        {
            "symbol": "USDT",
            "raw_data": {"items": [{"marginCoin": "USDT", "equity": "10000", "available": "9500"}]},
        }
    ]
    repo.reconcile_snapshot = {
        "details_json": {
            "drift": {"snapshot_health": {"missing_types": [], "stale_types": []}}
        }
    }
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    envelope = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "sig-5",
            "direction": "long",
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
            "recommended_leverage": 15,
            "qty_base": "0.01",
            "entry_price": "100",
            "stop_loss": "99.8",
            "take_profit": "109",
        },
    )

    result = service.handle_signal_event(envelope)

    assert result["decision_reason"] == "exit_plan_exceeds_allowed_leverage"
    assert result["payload_json"]["exit_preview"]["valid"] is False


def test_evaluate_intent_blocks_unknown_catalog_instrument(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    repo = _FakeRepo()
    service = LiveExecutionService(
        settings,
        _FakeExchangeClient(),
        repo,  # type: ignore[arg-type]
        catalog=_FakeCatalog([]),  # type: ignore[arg-type]
    )
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-catalog-1",
        symbol="ETHUSDT",
        direction="long",
        requested_runtime_mode="shadow",
        leverage=7,
        qty_base="0.01",
        entry_price="100",
        stop_loss="99",
        take_profit="102",
        payload={"signal_payload": {"trade_action": "allow_trade", "allowed_leverage": 7}},
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "instrument_unknown"


def _repo_with_clean_live_snapshots() -> _FakeRepo:
    repo = _FakeRepo()
    repo.snapshots["account"] = [
        {
            "symbol": "USDT",
            "raw_data": {
                "items": [{"marginCoin": "USDT", "equity": "10000", "available": "9500"}],
            },
        }
    ]
    repo.reconcile_snapshot = {
        "details_json": {"drift": {"snapshot_health": {"missing_types": [], "stale_types": []}}}
    }
    return repo


def test_evaluate_intent_blocks_on_online_drift_hard_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        STRATEGY_EXEC_MODE="auto",
        ENABLE_ONLINE_DRIFT_BLOCK="true",
        SHADOW_TRADE_ENABLE="false",
    )
    repo = _repo_with_clean_live_snapshots()
    repo.online_drift_state = {"effective_action": "hard_block"}
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-od-1",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 9,
            }
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "online_drift_hard_block"


def test_evaluate_intent_shadow_only_forces_shadow_on_live_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        STRATEGY_EXEC_MODE="auto",
        ENABLE_ONLINE_DRIFT_BLOCK="true",
        SHADOW_TRADE_ENABLE="false",
    )
    repo = _repo_with_clean_live_snapshots()
    repo.online_drift_state = {"effective_action": "shadow_only"}
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-od-2",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 9,
            }
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "online_drift_shadow_disabled"


def test_evaluate_intent_shadow_live_gate_blocks_high_signal_divergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        STRATEGY_EXEC_MODE="auto",
        SHADOW_TRADE_ENABLE="false",
        REQUIRE_SHADOW_MATCH_BEFORE_LIVE="true",
    )
    repo = _repo_with_clean_live_snapshots()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-sld-1",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
                "shadow_divergence_0_1": 0.99,
                "analysis_ts_ms": now_ms - 10_000,
            }
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "shadow_live_divergence_gate"
    sld = out["payload_json"]["shadow_live_divergence"]
    assert sld["match_ok"] is False
    assert "signal_shadow_model_divergence_high" in sld["hard_violations"]


def test_evaluate_intent_shadow_live_allows_when_aligned_with_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        STRATEGY_EXEC_MODE="auto",
        SHADOW_TRADE_ENABLE="false",
        REQUIRE_SHADOW_MATCH_BEFORE_LIVE="true",
    )
    repo = _repo_with_clean_live_snapshots()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-sld-2",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
                "shadow_divergence_0_1": 0.04,
                "analysis_ts_ms": now_ms - 10_000,
            }
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "live_candidate_recorded"
    sld = out["payload_json"]["shadow_live_divergence"]
    assert sld["match_ok"] is True
    assert out["payload_json"]["live_mirror_eligible"] is True


def test_evaluate_intent_live_blocks_when_meta_trade_lane_is_paper_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        STRATEGY_EXEC_MODE="auto",
        SHADOW_TRADE_ENABLE="false",
        REQUIRE_SHADOW_MATCH_BEFORE_LIVE="false",
    )
    repo = _repo_with_clean_live_snapshots()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-meta-paper",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "meta_trade_lane": "paper_only",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
                "shadow_divergence_0_1": 0.04,
                "analysis_ts_ms": now_ms - 10_000,
            }
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "meta_trade_lane_not_live_candidate"


def test_evaluate_intent_shadow_live_mismatch_without_gate_still_live_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        STRATEGY_EXEC_MODE="auto",
        SHADOW_TRADE_ENABLE="false",
        REQUIRE_SHADOW_MATCH_BEFORE_LIVE="false",
    )
    repo = _repo_with_clean_live_snapshots()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-sld-3",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
                "shadow_divergence_0_1": 0.99,
                "analysis_ts_ms": now_ms - 10_000,
            }
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "live_candidate_recorded"
    assert out["payload_json"]["shadow_live_divergence"]["match_ok"] is False
    assert out["payload_json"]["live_mirror_eligible"] is False


def test_evaluate_intent_blocks_spot_short_even_when_signal_allows_trade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RISK_MAX_POSITION_RISK_PCT", "0.5")
    settings = _settings(
        monkeypatch,
        BITGET_MARKET_FAMILY="spot",
        EXECUTION_MODE="shadow",
        SHADOW_TRADE_ENABLE="true",
        LIVE_ALLOWED_MARKET_FAMILIES="spot,futures,margin",
    )
    repo = _repo_with_clean_live_snapshots()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    spot_case = next(case for case in FAMILY_RUNTIME_CASES if case["name"] == "spot_btcusdt")
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-spot-short",
        symbol=spot_case["symbol"],
        market_family="spot",
        direction="short",
        requested_runtime_mode="shadow",
        leverage=7,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={"signal_payload": {"trade_action": "allow_trade", "allowed_leverage": 7}},
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "spot_short_not_supported"


def test_handle_signal_event_preserves_margin_family_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        BITGET_MARKET_FAMILY="margin",
        BITGET_MARGIN_ACCOUNT_MODE="crossed",
    )
    repo = _FakeRepo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    envelope = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "sig-margin-1",
            "direction": "long",
            "market_family": "margin",
            "margin_account_mode": "crossed",
            "trade_action": "allow_trade",
            "allowed_leverage": 7,
            "recommended_leverage": 7,
            "qty_base": "0.01",
            "entry_price": "50000",
            "stop_loss": "49500",
            "take_profit": "51000",
        },
    )

    out = service.handle_signal_event(envelope)

    assert out["payload_json"]["market_family"] == "margin"
    assert out["payload_json"]["margin_account_mode"] == "crossed"
    assert out["trace_json"]["market_family"] == "margin"
