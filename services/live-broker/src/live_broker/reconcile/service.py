from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from shared_py.eventbus import RedisStreamBus

from live_broker.config import LiveBrokerSettings
from live_broker.events import publish_system_alert
from live_broker.exchange_client import BitgetExchangeClient
from live_broker.persistence.repo import LiveBrokerRepository

logger = logging.getLogger("live_broker.reconcile")
_OPEN_ORDER_RECONCILE_LIMIT = 500
_RECENT_FILL_LIMIT = 500
_EXIT_PLAN_RECONCILE_LIMIT = 200
_ORDER_DRIFT_GRACE_SEC = 20
_POSITION_DRIFT_TOLERANCE = Decimal("0.00000001")
_FILL_DRIFT_TOLERANCE = Decimal("0.0000000001")
_SKIP_ACK_STATUSES = frozenset(
    {
        "",
        "created",
        "draft",
        "pending_create",
    }
)


class LiveReconcileService:
    def __init__(
        self,
        settings: LiveBrokerSettings,
        exchange_client: BitgetExchangeClient,
        repo: LiveBrokerRepository,
        *,
        bus: RedisStreamBus | None = None,
        private_rest: Any = None,
    ) -> None:
        self._settings = settings
        self._exchange_client = exchange_client
        self._repo = repo
        self._bus = bus
        self._private_rest = private_rest
        self._last_alert_status: str | None = None

    def run_once(
        self,
        *,
        reason: str,
        worker_telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema_ok, schema_detail = self._repo.schema_ready()
        decision_counts = self._repo.decision_action_counts() if schema_ok else {}
        exchange_state_expected = self._settings.private_exchange_access_enabled
        probe = (
            self._exchange_client.probe_exchange(private_rest=self._private_rest)
            if exchange_state_expected
            else {
                **self._exchange_client.describe(),
                "public_api_ok": None,
                "public_detail": "not_required",
                "private_api_configured": None,
                "private_detail": "not_required",
                "private_detail_de": "Privater Bitget-Zugriff ist fuer diesen Lauf nicht aktiv.",
                "private_auth_ok": None,
                "private_auth_detail": None,
                "private_auth_detail_de": None,
                "private_auth_classification": None,
                "private_auth_exchange_code": None,
                "market_snapshot": {},
            }
        )
        upstream_ok = True if not exchange_state_expected else bool(probe.get("public_api_ok"))
        keys_ok = bool(probe.get("private_api_configured"))
        auth_ok = probe.get("private_auth_ok")
        private_ok = True if not self._settings.live_order_submission_enabled else (
            keys_ok and auth_ok is True
        )

        status = "ok"
        if not schema_ok:
            status = "fail"
        elif exchange_state_expected and self._settings.live_require_exchange_health and not upstream_ok:
            status = "fail" if self._settings.execution_mode == "live" else "degraded"
        elif (
            self._settings.execution_mode == "live"
            and self._settings.live_order_submission_enabled
            and not private_ok
        ):
            status = "fail"

        recovery_state = self.restore_runtime_state() if schema_ok else {}
        drift_summary = (
            self._compute_drift_summary(
                recovery_state,
                worker_telemetry=worker_telemetry,
                exchange_state_expected=exchange_state_expected,
            )
            if schema_ok and exchange_state_expected
            else self._empty_drift_summary(exchange_state_expected=exchange_state_expected)
        )
        if status == "ok" and int(drift_summary.get("total_count") or 0) > 0:
            status = "degraded"

        if (
            exchange_state_expected
            and keys_ok
            and auth_ok is False
            and status == "ok"
        ):
            status = "degraded"

        reconcile_run_id: str | None = None
        if schema_ok:
            begun = self._repo.begin_reconcile_run(reason, {})
            reconcile_run_id = str(begun["reconcile_run_id"])

        try:
            snapshot = self._repo.record_reconcile_snapshot(
                {
                    "status": status,
                    "runtime_mode": self._settings.execution_mode,
                    "upstream_ok": upstream_ok and (
                        True if not self._settings.live_order_submission_enabled else private_ok
                    ),
                    "shadow_enabled": self._settings.shadow_path_active,
                    "live_submission_enabled": self._settings.live_order_submission_enabled,
                    "decision_counts_json": decision_counts,
                    "reconcile_run_id": reconcile_run_id,
                    "details_json": {
                        "reason": reason,
                        "reconcile_run_id": reconcile_run_id,
                        "schema_ok": schema_ok,
                        "schema_detail": schema_detail,
                        "execution_controls": {
                            "execution_mode": self._settings.execution_mode,
                            "strategy_execution_mode": self._settings.strategy_execution_mode,
                            "paper_path_active": self._settings.paper_path_active,
                            "shadow_trade_enable": self._settings.shadow_trade_enable,
                            "shadow_path_active": self._settings.shadow_path_active,
                            "live_trade_enable": self._settings.live_trade_enable,
                            "live_order_submission_enabled": self._settings.live_order_submission_enabled,
                            "exchange_state_expected": exchange_state_expected,
                            "safety_latch_active": self._repo.safety_latch_is_active(),
                            "live_safety_latch_on_reconcile_fail": (
                                self._settings.live_safety_latch_on_reconcile_fail
                            ),
                            "live_order_replace_enabled": self._settings.live_order_replace_enabled,
                            "require_shadow_match_before_live": (
                                self._settings.require_shadow_match_before_live
                            ),
                            "shadow_live_max_signal_shadow_divergence_0_1": (
                                self._settings.shadow_live_max_signal_shadow_divergence_0_1
                            ),
                            "shadow_live_max_timing_skew_ms": (
                                self._settings.shadow_live_max_timing_skew_ms
                            ),
                        },
                        "exchange_probe": probe,
                        "interfaces": {
                            "signal_engine_stream": self._settings.live_broker_signal_stream,
                            "paper_broker_reference_streams": self._settings.reference_streams,
                        },
                        "recovery_state": recovery_state,
                        "drift": drift_summary,
                    },
                }
            )
        except Exception:
            if reconcile_run_id is not None:
                try:
                    self._repo.complete_reconcile_run(reconcile_run_id, "failed", {})
                except Exception as exc:
                    logger.error(
                        "complete_reconcile_run failed_status run_id=%s err=%s",
                        reconcile_run_id,
                        exc,
                    )
            raise

        if reconcile_run_id is not None:
            try:
                self._repo.complete_reconcile_run(
                    reconcile_run_id,
                    "completed",
                    {"reconcile_snapshot_id": snapshot.get("reconcile_snapshot_id")},
                )
            except Exception as exc:
                logger.error(
                    "complete_reconcile_run failed run_id=%s err=%s",
                    reconcile_run_id,
                    exc,
                )
        self._publish_alert_if_needed(snapshot)
        self._maybe_arm_safety_latch_after_reconcile(
            status=str(snapshot.get("status") or ""),
            drift_total=int(drift_summary.get("total_count") or 0),
        )
        logger.info(
            "live-broker reconcile status=%s runtime_mode=%s upstream_ok=%s drift_count=%s",
            snapshot["status"],
            snapshot["runtime_mode"],
            snapshot["upstream_ok"],
            drift_summary.get("total_count"),
        )
        return snapshot

    def _maybe_arm_safety_latch_after_reconcile(
        self,
        *,
        status: str,
        drift_total: int,
    ) -> None:
        if not self._settings.live_safety_latch_on_reconcile_fail:
            return
        if not self._settings.live_order_submission_enabled:
            return
        if status != "fail":
            return
        if self._repo.safety_latch_is_active():
            return
        self._repo.record_audit_trail(
            {
                "category": "safety_latch",
                "action": "arm",
                "severity": "critical",
                "scope": "service",
                "scope_key": "reconcile",
                "source": "reconcile",
                "internal_order_id": None,
                "symbol": None,
                "details_json": {
                    "reason": "reconcile_fail_live_submission_enabled",
                    "reconcile_status": status,
                    "drift_total": drift_total,
                },
            }
        )
        if self._bus is None:
            return
        try:
            publish_system_alert(
                self._bus,
                alert_key="live-broker:safety-latch:armed:reconcile_fail",
                severity="critical",
                title="live-broker safety latch armed",
                message=(
                    "Reconcile=fail bei aktivem Live-Submit — automatischer Safety-Latch "
                    "(kein stilles Live ohne operatorisches release)."
                ),
                details={
                    "reconcile_status": status,
                    "drift_total": drift_total,
                },
            )
        except Exception as exc:
            logger.warning("safety latch alert publish failed: %s", exc)

    def latest_snapshot(self) -> dict[str, Any] | None:
        return self._repo.latest_reconcile_snapshot()

    def restore_runtime_state(self) -> dict[str, Any]:
        return self._repo.reconstruct_runtime_state(
            order_limit=_OPEN_ORDER_RECONCILE_LIMIT,
            fill_limit=_RECENT_FILL_LIMIT,
            journal_limit=self._settings.live_reconcile_journal_tail_limit,
            exit_plan_limit=_EXIT_PLAN_RECONCILE_LIMIT,
        )

    def _empty_drift_summary(self, *, exchange_state_expected: bool) -> dict[str, Any]:
        return {
            "total_count": 0,
            "order": {
                "local_only_count": 0,
                "exchange_only_count": 0,
                "local_only": [],
                "exchange_only": [],
            },
            "positions": {
                "mismatch_count": 0,
                "exchange_only_count": 0,
                "mismatches": [],
                "exchange_only": [],
            },
            "snapshot_health": {
                "missing_count": 0,
                "stale_count": 0,
                "missing_types": [],
                "stale_types": [],
                "stale_after_sec": max(45, self._settings.live_reconcile_interval_sec * 4),
                "exchange_state_expected": exchange_state_expected,
            },
            "divergence": self._empty_divergence_block(exchange_state_expected=exchange_state_expected),
        }

    def _empty_divergence_block(self, *, exchange_state_expected: bool) -> dict[str, Any]:
        return {
            "applicable": bool(exchange_state_expected),
            "missing_exchange_ack": {"count": 0, "orders": []},
            "journal_tail": {
                "recent_row_count": 0,
                "open_orders_latest_phase_submit_count": 0,
                "open_order_ids": [],
            },
            "fill_ledger": {"partial_drift_count": 0, "cases": []},
            "private_ws": {
                "applicable": bool(exchange_state_expected),
                "connection_state": None,
                "last_event_age_sec": None,
                "stale_while_connected": False,
                "disconnected_while_required": False,
                "enqueue_rest_catchup": False,
            },
            "exit_plans_restart": {},
            "degrade_increment_from_divergence": 0,
        }

    def _compute_drift_summary(
        self,
        recovery_state: dict[str, Any],
        *,
        worker_telemetry: dict[str, Any] | None,
        exchange_state_expected: bool,
    ) -> dict[str, Any]:
        local_orders = recovery_state.get("open_orders") or []
        exchange_order_snapshots = recovery_state.get("exchange_order_snapshots") or []
        exchange_position_snapshots = recovery_state.get("exchange_position_snapshots") or []
        exchange_account_snapshots = recovery_state.get("exchange_account_snapshots") or []
        recent_fills = recovery_state.get("recent_fills") or []

        exchange_open_orders = self._flatten_exchange_orders(exchange_order_snapshots)
        order_drift = self._compute_order_drift(local_orders, exchange_open_orders)
        local_positions = self._aggregate_local_positions(recent_fills)
        exchange_positions = self._aggregate_exchange_positions(exchange_position_snapshots)
        position_drift = self._compute_position_drift(local_positions, exchange_positions)
        snapshot_health = self._snapshot_health(
            exchange_order_snapshots,
            exchange_position_snapshots,
            exchange_account_snapshots,
        )

        divergence = self._compute_divergence_metrics(
            recovery_state,
            local_orders=local_orders,
            recent_fills=recent_fills,
            worker_telemetry=worker_telemetry,
            exchange_state_expected=exchange_state_expected,
        )
        div_incr = int(divergence.get("degrade_increment_from_divergence") or 0)

        total_count = (
            int(order_drift["local_only_count"])
            + int(order_drift["exchange_only_count"])
            + int(position_drift["mismatch_count"])
            + int(position_drift["exchange_only_count"])
            + int(snapshot_health["missing_count"])
            + int(snapshot_health["stale_count"])
            + div_incr
        )
        return {
            "total_count": total_count,
            "order": order_drift,
            "positions": position_drift,
            "snapshot_health": snapshot_health,
            "divergence": divergence,
        }

    def _compute_divergence_metrics(
        self,
        recovery_state: dict[str, Any],
        *,
        local_orders: list[dict[str, Any]],
        recent_fills: list[dict[str, Any]],
        worker_telemetry: dict[str, Any] | None,
        exchange_state_expected: bool,
    ) -> dict[str, Any]:
        base = self._empty_divergence_block(exchange_state_expected=exchange_state_expected)
        if not exchange_state_expected:
            return base

        journal_rows = list(recovery_state.get("execution_journal_recent") or [])
        open_ids = {str(o.get("internal_order_id")) for o in local_orders if o.get("internal_order_id")}

        missing_ack = self._orders_missing_exchange_ack(local_orders)
        base["missing_exchange_ack"] = {
            "count": len(missing_ack),
            "orders": missing_ack,
            "stale_after_sec": self._settings.live_reconcile_order_ack_stale_sec,
        }

        latest_phase_by_order = self._latest_journal_phase_per_order(journal_rows)
        phase_submit_open = sorted(
            oid
            for oid in open_ids
            if latest_phase_by_order.get(oid) == "order_submit"
        )
        base["journal_tail"] = {
            "recent_row_count": len(journal_rows),
            "open_orders_latest_phase_submit_count": len(phase_submit_open),
            "open_order_ids": phase_submit_open[:50],
        }

        fill_cases = self._partial_fill_divergence_cases(local_orders, recent_fills)
        base["fill_ledger"] = {
            "partial_drift_count": len(fill_cases),
            "cases": fill_cases[:40],
        }

        ws_block = self._private_ws_divergence(worker_telemetry)
        base["private_ws"] = ws_block

        exit_summary = recovery_state.get("active_exit_plans_summary") or {}
        base["exit_plans_restart"] = {
            "active_total": int(exit_summary.get("total") or 0),
            "by_state": exit_summary.get("by_state") or {},
            "persisted": True,
            "note": (
                "Exit-Plaene (stop/tp/runner) liegen in live.exit_plans; "
                "Operator-Release in live.execution_operator_releases + execution_journal."
            ),
        }

        incr = 0
        if self._settings.live_reconcile_missing_exchange_ack_degrades:
            incr += len(missing_ack)
        if self._settings.live_reconcile_fill_drift_degrades:
            incr += len(fill_cases)
        if self._settings.live_reconcile_ws_stale_contributes_to_drift:
            if ws_block.get("stale_while_connected") or ws_block.get("disconnected_while_required"):
                incr += 1
        base["degrade_increment_from_divergence"] = incr
        return base

    def _latest_journal_phase_per_order(
        self,
        journal_rows: list[dict[str, Any]],
    ) -> dict[str, str]:
        """journal_rows: neueste zuerst (wie list_recent_execution_journal)."""
        out: dict[str, str] = {}
        for row in journal_rows:
            oid = row.get("internal_order_id")
            if oid is None:
                continue
            key = str(oid)
            if key in out:
                continue
            out[key] = str(row.get("phase") or "")
        return out

    def _orders_missing_exchange_ack(
        self,
        local_orders: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        stale_sec = self._settings.live_reconcile_order_ack_stale_sec
        out: list[dict[str, Any]] = []
        for order in local_orders:
            ex_id = str(order.get("exchange_order_id") or "").strip()
            if ex_id:
                continue
            st = str(order.get("status") or "").strip().lower()
            if st in _SKIP_ACK_STATUSES:
                continue
            updated_at = self._parse_ts(order.get("updated_ts")) or self._parse_ts(
                order.get("created_ts")
            )
            if updated_at is None:
                continue
            if (now - updated_at).total_seconds() < stale_sec:
                continue
            out.append(
                {
                    "internal_order_id": order.get("internal_order_id"),
                    "client_oid": order.get("client_oid"),
                    "status": order.get("status"),
                    "last_action": order.get("last_action"),
                    "symbol": order.get("symbol"),
                    "age_sec": int((now - updated_at).total_seconds()),
                }
            )
        return out

    def _partial_fill_divergence_cases(
        self,
        local_orders: list[dict[str, Any]],
        recent_fills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        filled_by_order: dict[str, Decimal] = {}
        for fill in recent_fills:
            oid = fill.get("internal_order_id")
            if oid is None:
                continue
            key = str(oid)
            sz = self._to_decimal(fill.get("size"))
            if sz is None:
                continue
            filled_by_order[key] = filled_by_order.get(key, Decimal("0")) + sz

        open_by_id = {str(o["internal_order_id"]): o for o in local_orders if o.get("internal_order_id")}
        cases: list[dict[str, Any]] = []
        for oid, filled_sum in filled_by_order.items():
            order = open_by_id.get(oid)
            if order is None:
                continue
            order_sz = self._to_decimal(order.get("size"))
            if order_sz is None or order_sz <= 0:
                continue
            if filled_sum <= 0:
                continue
            st = str(order.get("status") or "").lower()
            if "fill" in st or "partial" in st:
                continue
            if filled_sum + _FILL_DRIFT_TOLERANCE < order_sz:
                cases.append(
                    {
                        "internal_order_id": oid,
                        "symbol": order.get("symbol"),
                        "order_status": order.get("status"),
                        "order_size": format(order_sz, "f"),
                        "filled_sum_recent_window": format(filled_sum, "f"),
                    }
                )
        return cases

    def _private_ws_divergence(self, worker_telemetry: dict[str, Any] | None) -> dict[str, Any]:
        ws = (worker_telemetry or {}).get("private_ws") if worker_telemetry else None
        if not isinstance(ws, dict):
            return {
                "applicable": True,
                "connection_state": None,
                "last_event_age_sec": None,
                "stale_while_connected": False,
                "disconnected_while_required": False,
                "enqueue_rest_catchup": False,
            }
        now_ms = int(time.time() * 1000)
        last_ev = ws.get("last_event_ts_ms")
        age_sec: float | None = None
        if last_ev is not None:
            try:
                age_sec = max(0.0, (now_ms - int(last_ev)) / 1000.0)
            except (TypeError, ValueError):
                age_sec = None
        conn = str(ws.get("connection_state") or "")
        stale_thr = float(self._settings.live_reconcile_private_ws_stale_sec)
        connected = conn == "connected"
        stale_while_connected = bool(connected and age_sec is not None and age_sec > stale_thr)
        live_sub = self._settings.live_order_submission_enabled
        disconnected_while_required = bool(live_sub and conn not in ("connected", "connecting"))
        enqueue = bool(
            self._settings.live_reconcile_rest_catchup_on_ws_stale
            and (stale_while_connected or disconnected_while_required)
        )
        return {
            "applicable": True,
            "connection_state": conn or None,
            "last_event_age_sec": age_sec,
            "received_events": ws.get("received_events"),
            "reconnect_count": ws.get("reconnect_count"),
            "stale_while_connected": stale_while_connected,
            "disconnected_while_required": disconnected_while_required,
            "enqueue_rest_catchup": enqueue,
        }

    def _compute_order_drift(
        self,
        local_orders: list[dict[str, Any]],
        exchange_open_orders: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        local_index: dict[str, dict[str, Any]] = {}
        exchange_index: dict[str, dict[str, Any]] = {}
        for order in local_orders:
            key = self._order_key(order)
            if key is not None:
                local_index[key] = order
        for item in exchange_open_orders:
            key = self._exchange_order_key(item)
            if key is not None:
                exchange_index[key] = item

        local_only: list[dict[str, Any]] = []
        for key, order in local_index.items():
            if key in exchange_index:
                continue
            updated_at = self._parse_ts(order.get("updated_ts")) or self._parse_ts(order.get("created_ts"))
            if updated_at is not None and (now - updated_at).total_seconds() < _ORDER_DRIFT_GRACE_SEC:
                continue
            local_only.append(
                {
                    "internal_order_id": order.get("internal_order_id"),
                    "client_oid": order.get("client_oid"),
                    "exchange_order_id": order.get("exchange_order_id"),
                    "symbol": order.get("symbol"),
                    "status": order.get("status"),
                }
            )

        exchange_only = [
            {
                "client_oid": item.get("clientOid"),
                "exchange_order_id": item.get("orderId"),
                "symbol": item.get("instId"),
                "status": item.get("status"),
            }
            for key, item in exchange_index.items()
            if key not in local_index
        ]
        return {
            "local_only_count": len(local_only),
            "exchange_only_count": len(exchange_only),
            "local_only": local_only,
            "exchange_only": exchange_only,
        }

    def _compute_position_drift(
        self,
        local_positions: dict[str, Decimal],
        exchange_positions: dict[str, Decimal],
    ) -> dict[str, Any]:
        mismatches: list[dict[str, Any]] = []
        exchange_only: list[dict[str, Any]] = []
        symbols = sorted(set(local_positions) | set(exchange_positions))
        for symbol in symbols:
            local_value = local_positions.get(symbol, Decimal("0"))
            exchange_value = exchange_positions.get(symbol, Decimal("0"))
            if symbol not in local_positions and exchange_value.copy_abs() > _POSITION_DRIFT_TOLERANCE:
                exchange_only.append(
                    {
                        "symbol": symbol,
                        "exchange_net_size": format(exchange_value, "f"),
                    }
                )
                continue
            if (local_value - exchange_value).copy_abs() > _POSITION_DRIFT_TOLERANCE:
                mismatches.append(
                    {
                        "symbol": symbol,
                        "local_net_size": format(local_value, "f"),
                        "exchange_net_size": format(exchange_value, "f"),
                    }
                )
        return {
            "mismatch_count": len(mismatches),
            "exchange_only_count": len(exchange_only),
            "mismatches": mismatches,
            "exchange_only": exchange_only,
        }

    def _snapshot_health(
        self,
        order_snapshots: list[dict[str, Any]],
        position_snapshots: list[dict[str, Any]],
        account_snapshots: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        stale_after_sec = max(45, self._settings.live_reconcile_interval_sec * 4)
        per_type = {
            "orders": order_snapshots,
            "positions": position_snapshots,
            "account": account_snapshots,
        }
        stale: list[str] = []
        missing: list[str] = []
        for snapshot_type, items in per_type.items():
            if not items:
                missing.append(snapshot_type)
                continue
            timestamps = [
                parsed
                for item in items
                if (parsed := self._parse_ts(item.get("created_ts"))) is not None
            ]
            latest = max(timestamps, default=None)
            if latest is None:
                stale.append(snapshot_type)
                continue
            if (now - latest).total_seconds() > stale_after_sec:
                stale.append(snapshot_type)
        return {
            "missing_count": len(missing),
            "stale_count": len(stale),
            "missing_types": missing,
            "stale_types": stale,
            "stale_after_sec": stale_after_sec,
        }

    def _flatten_exchange_orders(
        self,
        snapshots: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for snapshot in snapshots:
            raw = snapshot.get("raw_data") or {}
            items = raw.get("items") if isinstance(raw, dict) else None
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status") or "").lower()
                if status in {"canceled", "filled"}:
                    continue
                out.append(item)
        return out

    def _aggregate_local_positions(
        self,
        fills: list[dict[str, Any]],
    ) -> dict[str, Decimal]:
        positions: dict[str, Decimal] = {}
        for fill in fills:
            symbol = str(fill.get("symbol") or "").strip()
            if not symbol:
                continue
            raw = fill.get("raw_json") or {}
            trade_side = str(raw.get("tradeSide") or "").strip().lower()
            side = str(fill.get("side") or "").strip().lower()
            size = self._to_decimal(fill.get("size"))
            if size is None:
                continue
            delta = self._fill_delta(side=side, trade_side=trade_side, size=size)
            positions[symbol] = positions.get(symbol, Decimal("0")) + delta
        return positions

    def _aggregate_exchange_positions(
        self,
        snapshots: list[dict[str, Any]],
    ) -> dict[str, Decimal]:
        positions: dict[str, Decimal] = {}
        for snapshot in snapshots:
            raw = snapshot.get("raw_data") or {}
            items = raw.get("items") if isinstance(raw, dict) else None
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("instId") or snapshot.get("symbol") or "").strip()
                if not symbol:
                    continue
                total = self._to_decimal(item.get("total"))
                if total is None:
                    continue
                hold_side = str(item.get("holdSide") or "").strip().lower()
                sign = Decimal("1")
                if hold_side == "short":
                    sign = Decimal("-1")
                positions[symbol] = positions.get(symbol, Decimal("0")) + (sign * total)
        return positions

    def _fill_delta(
        self,
        *,
        side: str,
        trade_side: str,
        size: Decimal,
    ) -> Decimal:
        if not trade_side:
            return size if side == "buy" else -size
        is_open = (
            "open" in trade_side
            or trade_side in {"buy_single", "sell_single"}
        )
        if is_open:
            return size if side == "buy" else -size
        return -size if side == "sell" else size

    def _order_key(self, order: dict[str, Any]) -> str | None:
        client_oid = order.get("client_oid")
        if client_oid:
            return f"client_oid:{client_oid}"
        exchange_order_id = order.get("exchange_order_id")
        if exchange_order_id:
            return f"order_id:{exchange_order_id}"
        return None

    def _exchange_order_key(self, item: dict[str, Any]) -> str | None:
        client_oid = item.get("clientOid")
        if client_oid:
            return f"client_oid:{client_oid}"
        order_id = item.get("orderId")
        if order_id:
            return f"order_id:{order_id}"
        return None

    def _to_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _parse_ts(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    def _publish_alert_if_needed(self, snapshot: dict[str, Any]) -> None:
        if self._bus is None:
            return
        status = str(snapshot["status"])
        if status == "ok":
            self._last_alert_status = None
            return
        if self._last_alert_status == status:
            return
        severity = "critical" if status == "fail" else "warn"
        publish_system_alert(
            self._bus,
            alert_key=f"live-broker:reconcile:{status}",
            severity=severity,
            title="live-broker reconcile degraded",
            message=(
                "Live broker readiness ist nicht vollstaendig. "
                f"runtime_mode={snapshot['runtime_mode']} status={status}"
            ),
            details={
                "runtime_mode": snapshot["runtime_mode"],
                "upstream_ok": snapshot["upstream_ok"],
                "details": snapshot.get("details_json"),
            },
        )
        self._last_alert_status = status
