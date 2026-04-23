from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import random
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from shared_py.billing_wallet import fetch_prepaid_balance_list_usd, prepaid_allows_new_trade
from shared_py.modul_mate_db_gates import assert_execution_allowed, fetch_tenant_modul_mate_gates
from shared_py.product_policy import (
    ExecutionPolicyViolationError,
    demo_trading_allowed,
    live_trading_allowed,
    order_placement_permissions,
)
from shared_py.bitget import (
    BitgetInstrumentCatalog,
    BitgetInstrumentMetadataService,
    UnknownInstrumentError,
)
from shared_py.bitget.execution_guards import (
    market_spread_slippage_cap_reasons,
    preset_stop_distance_floor_reasons,
    preset_stop_vs_spread_reasons,
    reduce_only_position_consistency_reasons,
    replace_size_safety_reasons,
)
from shared_py.bitget.instruments import BitgetEndpointProfile, MarginAccountMode, endpoint_profile_for
from shared_py.eventbus import RedisStreamBus
from shared_py.observability.execution_forensic import redact_nested_mapping

from live_broker.config import LiveBrokerSettings
from live_broker.control_plane.capabilities import assert_write_capability
from live_broker.events import publish_system_alert
from live_broker.orders.passive_order_manager import (
    chase_price_within_slippage,
    coalesce_orderflow_imbalance,
    orderflow_wall_against_side,
    passive_limit_price,
    passive_maker_trace_enabled,
    passive_params_from_sources,
    passive_anchor_decimal,
    plan_iceberg_sizes,
)
from live_broker.orders.models import (
    CancelAllOrdersRequest,
    EmergencyFlattenRequest,
    KillSwitchRequest,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderQueryRequest,
    OrderReplaceRequest,
    ReduceOnlyOrderRequest,
    SafetyLatchReleaseRequest,
)
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_rest import (
    BitgetPrivateRestClient,
    BitgetRestError,
    BitgetRestResponse,
)

if TYPE_CHECKING:
    from live_broker.exchange_client import BitgetExchangeClient
    from live_broker.exits.service import LiveExitService

logger = logging.getLogger("live_broker.orders")
_SERVICE_SCOPE_KEY = "service"
_OPEN_ORDER_SCAN_LIMIT = 500

_DEAD_LETTER_CLASSIFICATIONS = frozenset(
    {
        "operator_intervention",
        "auth",
        "permission",
        "kill_switch",
    }
)


def client_oid_for_internal_order(
    prefix: str,
    *,
    action_tag: str,
    internal_order_id: UUID,
) -> str:
    client_oid = f"{prefix}-{action_tag}-{internal_order_id.hex}"
    if len(client_oid) > 50:
        raise ValueError("clientOid darf Bitget-konform maximal 50 Zeichen haben")
    return client_oid


class LiveBrokerOrderService:
    def __init__(
        self,
        settings: LiveBrokerSettings,
        repo: LiveBrokerRepository,
        private_client: BitgetPrivateRestClient,
        *,
        bus: RedisStreamBus | None = None,
        catalog: BitgetInstrumentCatalog | None = None,
        metadata_service: BitgetInstrumentMetadataService | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._private = private_client
        self._bus = bus
        self._catalog = catalog
        self._metadata_service = metadata_service
        self._exit_service: LiveExitService | None = None
        self._exchange_client: BitgetExchangeClient | None = None

    def set_exchange_client(self, client: "BitgetExchangeClient | None") -> None:
        self._exchange_client = client

    def set_exit_service(self, exit_service: "LiveExitService") -> None:
        self._exit_service = exit_service

    def trade_root_internal_order_id(self, internal_order_id: str) -> str:
        return self._trade_root_internal_order_id(internal_order_id)

    def _assert_prepaid_allows_opening_order(
        self,
        request: OrderCreateRequest,
        *,
        allow_safety_bypass: bool,
    ) -> None:
        if allow_safety_bypass or request.reduce_only:
            return
        if not self._settings.billing_prepaid_gate_enabled:
            return
        dsn = (self._settings.database_url or "").strip()
        if not dsn:
            return
        tid = (self._settings.billing_prepaid_tenant_id or "default").strip()
        min_act = Decimal(str(self._settings.billing_min_balance_new_trade_usd.strip() or "50"))
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            bal = fetch_prepaid_balance_list_usd(conn, tenant_id=tid)
        ok, msg = prepaid_allows_new_trade(bal, min_activation_usd=min_act)
        if not ok:
            raise BitgetRestError(
                classification="billing_blocked",
                message=msg,
                retryable=False,
            )

    def _assert_modul_mate_policy_allows_exchange_submit(
        self,
        *,
        allow_safety_bypass: bool,
    ) -> None:
        if allow_safety_bypass:
            return
        if not self._settings.commercial_gates_enforced_for_exchange_submit:
            return
        dsn = (self._settings.database_url or "").strip()
        tid = (self._settings.modul_mate_gate_tenant_id or "default").strip()
        if not dsn:
            raise BitgetRestError(
                classification="service_misconfigured",
                message="commercial_gates_require_database_url",
                retryable=False,
            )
        mode = "DEMO" if self._settings.bitget_demo_enabled else "LIVE"
        try:
            with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
                assert_execution_allowed(conn, tenant_id=tid, mode=mode)
        except ExecutionPolicyViolationError as pe:
            self._modul_mate_violation_audit(
                exc=pe, tenant_id=tid, bitget_demo_enabled=self._settings.bitget_demo_enabled
            )
            if pe.reason == "tenant_modul_mate_gates_missing":
                raise BitgetRestError(
                    classification="policy_blocked",
                    message=(
                        f"modul_mate_gates_missing: kein Eintrag fuer tenant_id={tid!r} "
                        "in app.tenant_modul_mate_gates"
                    ),
                    retryable=False,
                ) from pe
            if pe.reason == "no_active_commercial_contract" and mode == "LIVE":
                raise BitgetRestError(
                    classification="policy_blocked",
                    message=(
                        f"no_active_commercial_contract: fehlender oder nicht "
                        f"abgeschlossener contract_workflow fuer tenant_id={tid!r} (LIVE)"
                    ),
                    retryable=False,
                ) from pe
            if mode == "DEMO":
                raise BitgetRestError(
                    classification="policy_blocked",
                    message="modul_mate_demo_trading_not_permitted",
                    retryable=False,
                ) from pe
            raise BitgetRestError(
                classification="policy_blocked",
                message="modul_mate_live_trading_not_permitted",
                retryable=False,
            ) from pe

    def _modul_mate_violation_audit(
        self,
        *,
        exc: ExecutionPolicyViolationError,
        tenant_id: str,
        bitget_demo_enabled: bool,
    ) -> None:
        dsn = (self._settings.database_url or "").strip()
        if not dsn:
            return
        try:
            with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3) as conn:
                gates = fetch_tenant_modul_mate_gates(conn, tenant_id=tenant_id)
        except Exception as exc_db:
            self._record_audit(
                category="commercial_gate",
                action="denied",
                severity="critical",
                scope="tenant",
                scope_key=tenant_id,
                source="live-broker",
                internal_order_id=None,
                symbol=None,
                details={
                    "reason": "audit_snapshot_failed",
                    "tenant_id": tenant_id,
                    "policy_violation_reason": exc.reason,
                    "err": str(exc_db)[:200],
                },
            )
            return
        if gates is None:
            gate_snapshot = {
                "reason": "tenant_modul_mate_gates_missing",
                "policy_violation_reason": exc.reason,
                "tenant_id": tenant_id,
                "bitget_demo_enabled": bitget_demo_enabled,
            }
        else:
            perms = order_placement_permissions(gates)
            gate_snapshot = {
                "tenant_id": tenant_id,
                "gates": asdict(gates),
                "can_place_demo_orders": perms.can_place_demo_orders,
                "can_place_live_orders": perms.can_place_live_orders,
                "commercial_execution_mode": perms.commercial_execution_mode.value,
                "bitget_demo_enabled": bitget_demo_enabled,
                "policy_violation_reason": exc.reason,
            }
        self._record_audit(
            category="commercial_gate",
            action="denied",
            severity="critical",
            scope="tenant",
            scope_key=tenant_id,
            source="live-broker",
            internal_order_id=None,
            symbol=None,
            details=gate_snapshot,
        )

    def create_order(
        self,
        request: OrderCreateRequest,
        *,
        priority: bool = False,
        allow_safety_bypass: bool = False,
    ) -> dict[str, Any]:
        return self._create_order(
            request,
            action="create",
            action_tag="crt",
            priority=priority,
            allow_safety_bypass=allow_safety_bypass,
        )

    def create_reduce_only_order(
        self,
        request: ReduceOnlyOrderRequest,
        *,
        priority: bool = False,
        allow_safety_bypass: bool = False,
    ) -> dict[str, Any]:
        request.reduce_only = True
        return self._create_order(
            request,
            action="reduce_only",
            action_tag="rdc",
            priority=priority,
            allow_safety_bypass=allow_safety_bypass,
        )

    def cancel_order(
        self,
        request: OrderCancelRequest,
        *,
        priority: bool = False,
    ) -> dict[str, Any]:
        identity = self._resolve_identity(request.internal_order_id, request.order_id, request.client_oid)
        symbol = request.symbol or identity.get("symbol")
        product_type = request.product_type or identity.get("product_type") or self._settings.product_type
        if not symbol:
            raise BitgetRestError(
                classification="validation",
                message="cancel_order braucht symbol oder ein lokales internal_order_id mit Symbol",
                retryable=False,
            )
        margin_coin = request.margin_coin or identity.get("margin_coin") or self._settings.effective_margin_coin
        order_family = str(
            request.market_family
            or identity.get("market_family")
            or self._settings.market_family
        ).lower()
        ma_mode = identity.get("margin_account_mode")
        if order_family == "margin" and not ma_mode:
            ma_mode = self._settings.margin_account_mode
        profile = self._order_endpoint_profile(order_family, str(ma_mode).lower() if ma_mode else None)
        assert_write_capability(profile, "order_cancel")
        cancel_path = profile.private_cancel_order_path or "/api/v2/mix/order/cancel-order"
        body = self._build_cancel_body(
            symbol=symbol,
            product_type=product_type,
            margin_coin=margin_coin,
            market_family=order_family,
        )
        if identity.get("exchange_order_id"):
            body["orderId"] = identity["exchange_order_id"]
        elif identity.get("client_oid"):
            body["clientOid"] = identity["client_oid"]
        else:
            raise BitgetRestError(
                classification="validation",
                message="cancel_order braucht orderId oder clientOid",
                retryable=False,
            )
        response = self._call_private(
            internal_order_id=identity["internal_order_id"],
            action="cancel",
            request_path=cancel_path,
            request_json=body,
            call=lambda: self._private.cancel_order(
                body, priority=priority, request_path=cancel_path
            ),
            client_oid=identity.get("client_oid"),
            exchange_order_id=identity.get("exchange_order_id"),
        )
        stored = self._repo.upsert_order(
            {
                **identity,
                "internal_order_id": identity["internal_order_id"],
                "parent_internal_order_id": identity.get("parent_internal_order_id"),
                "source_service": identity.get("source_service") or "live-broker",
                "symbol": symbol,
                "product_type": product_type,
                "margin_mode": identity.get("margin_mode") or "isolated",
                "margin_coin": margin_coin,
                "side": identity.get("side") or "buy",
                "trade_side": identity.get("trade_side"),
                "order_type": identity.get("order_type") or "limit",
                "force": identity.get("force"),
                "reduce_only": bool(identity.get("reduce_only")),
                "size": identity.get("size") or "0.00000001",
                "price": identity.get("price"),
                "note": identity.get("note") or "",
                "client_oid": identity.get("client_oid") or response.payload.get("data", {}).get("clientOid"),
                "exchange_order_id": identity.get("exchange_order_id") or response.payload.get("data", {}).get("orderId"),
                "status": "canceled",
                "last_action": "cancel",
                "last_http_status": response.http_status,
                "last_exchange_code": str(response.payload.get("code") or ""),
                "last_exchange_msg": str(response.payload.get("msg") or ""),
                "last_response_json": response.payload,
                "trace_json": {
                    **(identity.get("trace_json") or {}),
                    **request.trace,
                },
            }
        )
        if self._exit_service is not None:
            self._exit_service.on_order_canceled(order=stored)
        return {"ok": True, "item": stored, "exchange": self._response_to_dict(response)}

    def replace_order(
        self,
        request: OrderReplaceRequest,
        *,
        priority: bool = False,
    ) -> dict[str, Any]:
        if not self._settings.live_order_replace_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_ORDER_REPLACE_ENABLED=false (Replace-Blockade)",
                retryable=False,
            )
        if self._repo.safety_latch_is_active():
            raise BitgetRestError(
                classification="kill_switch",
                message="Safety latch aktiv — replace blockiert bis operatorisches release",
                retryable=False,
            )
        if not self._settings.live_order_submission_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_TRADE_ENABLE=false",
                retryable=False,
            )
        self._assert_submit_runtime_gates(allow_safety_bypass=False, operation="replace")
        existing = self._require_local_order(str(request.internal_order_id))
        if request.new_price is not None:
            tj = dict(existing.get("trace_json") or {})
            pm = tj.get("predatory_passive_maker")
            if isinstance(pm, dict) and pm.get("enabled") and pm.get("rewritten_from") == "market":
                anchor = passive_anchor_decimal(tj, str(existing.get("price") or ""))
                if anchor is not None and anchor > 0:
                    np = self._to_decimal(request.new_price)
                    if np is not None:
                        params = passive_params_from_sources(
                            settings_max_slippage_bps=self._settings.live_passive_max_slippage_bps_default,
                            settings_slices=self._settings.live_passive_iceberg_slices_default,
                            settings_imbalance_pause_ms=self._settings.live_passive_imbalance_pause_ms,
                            settings_imbalance_threshold=self._settings.live_passive_imbalance_against_threshold,
                            trace=tj,
                        )
                        if not chase_price_within_slippage(
                            anchor_price=anchor,
                            new_limit_price=np,
                            max_slippage_bps=params.max_slippage_bps,
                        ):
                            raise BitgetRestError(
                                classification="validation",
                                message=(
                                    "passive_maker_chase_exceeds_max_slippage: "
                                    f"anchor={anchor} new_price={np} max_bps={params.max_slippage_bps}"
                                ),
                                retryable=False,
                            )
        self._assert_kill_switch_allows_existing_order(existing, operation="replace")
        new_internal_order_id = request.new_internal_order_id or uuid4()
        existing_new = self._repo.get_order_by_internal_id(str(new_internal_order_id))
        if existing_new is not None:
            return {"ok": True, "idempotent": True, "item": existing_new}
        rep_reasons = replace_size_safety_reasons(
            existing_reduce_only=bool(existing.get("reduce_only")),
            old_size=self._to_decimal(existing.get("size")),
            new_size=self._to_decimal(request.new_size),
        )
        if rep_reasons:
            raise BitgetRestError(
                classification="validation",
                message=rep_reasons[0],
                retryable=False,
            )
        new_client_oid = client_oid_for_internal_order(
            self._settings.order_idempotency_prefix,
            action_tag="rpl",
            internal_order_id=new_internal_order_id,
        )
        body = {
            "symbol": existing["symbol"],
            "productType": existing["product_type"],
            "newClientOid": new_client_oid,
        }
        if existing.get("exchange_order_id"):
            body["orderId"] = existing["exchange_order_id"]
        else:
            body["clientOid"] = existing["client_oid"]
        if existing.get("margin_coin"):
            body["marginCoin"] = existing["margin_coin"]
        if request.new_size is not None:
            body["newSize"] = request.new_size
            if request.new_price is not None:
                body["newPrice"] = request.new_price
        if request.new_preset_stop_surplus_price is not None:
            body["newPresetStopSurplusPrice"] = request.new_preset_stop_surplus_price
        if request.new_preset_stop_loss_price is not None:
            body["newPresetStopLossPrice"] = request.new_preset_stop_loss_price
        fam = str(existing.get("market_family") or self._settings.market_family).lower()
        ma_mode = existing.get("margin_account_mode")
        profile = self._order_endpoint_profile(
            fam,
            str(ma_mode).lower() if ma_mode else None,
        )
        assert_write_capability(profile, "order_replace")
        mod_path = profile.private_modify_order_path
        if not mod_path:
            raise BitgetRestError(
                classification="service_disabled",
                message=f"Order-Replace (modify) fuer market_family={fam} nicht unterstuetzt",
                retryable=False,
            )
        response = self._call_private(
            internal_order_id=str(new_internal_order_id),
            action="replace",
            request_path=mod_path,
            request_json=body,
            call=lambda: self._private.modify_order(
                body, priority=priority, request_path=mod_path
            ),
            client_oid=new_client_oid,
            exchange_order_id=existing.get("exchange_order_id"),
        )
        detail = self._query_remote_detail(
            symbol=existing["symbol"],
            product_type=existing["product_type"],
            client_oid=new_client_oid,
            market_family=fam,
            margin_account_mode=str(ma_mode).lower() if ma_mode else None,
        )
        self._repo.upsert_order(
            {
                **existing,
                "internal_order_id": existing["internal_order_id"],
                "parent_internal_order_id": existing.get("parent_internal_order_id"),
                "status": "replaced",
                "last_action": "replace",
                "last_http_status": response.http_status,
                "last_exchange_code": str(response.payload.get("code") or ""),
                "last_exchange_msg": str(response.payload.get("msg") or ""),
                "last_response_json": response.payload,
                "trace_json": existing.get("trace_json") or {},
            }
        )
        stored = self._repo.upsert_order(
            {
                "internal_order_id": str(new_internal_order_id),
                "parent_internal_order_id": existing["internal_order_id"],
                "source_service": existing.get("source_service") or "live-broker",
                "symbol": existing["symbol"],
                "product_type": existing["product_type"],
                "margin_mode": existing["margin_mode"],
                "margin_coin": existing["margin_coin"],
                "market_family": existing.get("market_family"),
                "margin_account_mode": existing.get("margin_account_mode"),
                "source_execution_decision_id": existing.get("source_execution_decision_id"),
                "side": existing["side"],
                "trade_side": existing.get("trade_side"),
                "order_type": existing["order_type"],
                "force": existing.get("force"),
                "reduce_only": bool(existing.get("reduce_only")),
                "size": request.new_size or existing["size"],
                "price": request.new_price or existing.get("price"),
                "note": request.note or existing.get("note") or "",
                "client_oid": new_client_oid,
                "exchange_order_id": self._extract_exchange_order_id(response.payload, detail),
                "status": self._extract_order_state(detail) or "replace_ack",
                "last_action": "replace",
                "last_http_status": response.http_status,
                "last_exchange_code": str(response.payload.get("code") or ""),
                "last_exchange_msg": str(response.payload.get("msg") or ""),
                "last_response_json": detail.payload if detail is not None else response.payload,
                "trace_json": {
                    **(existing.get("trace_json") or {}),
                    **request.trace,
                },
            }
        )
        if self._exit_service is not None:
            self._exit_service.on_order_replaced(
                existing_order=existing,
                new_order=stored,
                request=request,
            )
        return {
            "ok": True,
            "item": stored,
            "exchange": self._response_to_dict(response),
            "detail": self._response_to_dict(detail) if detail is not None else None,
        }

    def query_order(self, request: OrderQueryRequest) -> dict[str, Any]:
        identity = self._resolve_identity(request.internal_order_id, request.order_id, request.client_oid)
        symbol = request.symbol or identity.get("symbol")
        product_type = request.product_type or identity.get("product_type") or self._settings.product_type
        if not symbol:
            raise BitgetRestError(
                classification="validation",
                message="query_order braucht symbol oder ein lokales internal_order_id mit Symbol",
                retryable=False,
            )
        order_family = str(
            request.market_family
            or identity.get("market_family")
            or self._settings.market_family
        ).lower()
        ma_mode = identity.get("margin_account_mode")
        profile = self._order_endpoint_profile(
            order_family,
            str(ma_mode).lower() if ma_mode else None,
        )
        detail_path = (
            profile.private_order_detail_path
            or profile.private_open_orders_path
            or "/api/v2/mix/order/detail"
        )
        params = self._build_query_params(
            symbol=symbol, product_type=product_type, market_family=order_family
        )
        if identity.get("exchange_order_id"):
            params["orderId"] = identity["exchange_order_id"]
        elif identity.get("client_oid"):
            params["clientOid"] = identity["client_oid"]
        else:
            raise BitgetRestError(
                classification="validation",
                message="query_order braucht orderId oder clientOid",
                retryable=False,
            )
        response = self._call_private(
            internal_order_id=identity["internal_order_id"],
            action="query",
            request_path=detail_path,
            request_json=params,
            call=lambda: self._private.get_order_detail(
                params=params,
                request_path=detail_path,
                market_family=order_family,
            ),
            client_oid=identity.get("client_oid"),
            exchange_order_id=identity.get("exchange_order_id"),
        )
        data = response.payload.get("data") if isinstance(response.payload, dict) else {}
        if not isinstance(data, dict):
            data = {}
        stored = self._repo.upsert_order(
            {
                "internal_order_id": identity["internal_order_id"],
                "parent_internal_order_id": identity.get("parent_internal_order_id"),
                "source_service": identity.get("source_service") or "live-broker",
                "symbol": symbol,
                "product_type": product_type,
                "margin_mode": identity.get("margin_mode") or (data.get("marginMode") or "isolated"),
                "margin_coin": identity.get("margin_coin") or (data.get("marginCoin") or self._settings.effective_margin_coin),
                "side": identity.get("side") or (data.get("side") or "buy"),
                "trade_side": identity.get("trade_side") or data.get("tradeSide"),
                "order_type": identity.get("order_type") or (data.get("orderType") or "limit"),
                "force": identity.get("force") or data.get("force"),
                "reduce_only": self._extract_reduce_only(data, identity.get("reduce_only")),
                "size": identity.get("size") or (data.get("size") or "0.00000001"),
                "price": identity.get("price") or data.get("price"),
                "note": identity.get("note") or "",
                "client_oid": data.get("clientOid") or identity.get("client_oid"),
                "exchange_order_id": data.get("orderId") or identity.get("exchange_order_id"),
                "status": self._extract_order_state(response) or identity.get("status") or "unknown",
                "last_action": "query",
                "last_http_status": response.http_status,
                "last_exchange_code": str(response.payload.get("code") or ""),
                "last_exchange_msg": str(response.payload.get("msg") or ""),
                "last_response_json": response.payload,
                "trace_json": identity.get("trace_json") or {},
            }
        )
        return {"ok": True, "item": stored, "exchange": self._response_to_dict(response)}

    def list_recent_orders(self, limit: int) -> list[dict[str, Any]]:
        return self._repo.list_recent_orders(limit)

    def list_recent_order_actions(self, limit: int) -> list[dict[str, Any]]:
        return self._repo.list_recent_order_actions(limit)

    def list_recent_kill_switch_events(
        self,
        limit: int,
        *,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        return self._repo.list_recent_kill_switch_events(limit, active_only=active_only)

    def list_active_kill_switches(self) -> list[dict[str, Any]]:
        return self._repo.active_kill_switches()

    def list_recent_audit_trails(self, limit: int) -> list[dict[str, Any]]:
        return self._repo.list_recent_audit_trails(limit)

    def list_recent_audit_trails_filtered(
        self,
        limit: int,
        *,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._repo.list_recent_audit_trails(limit, category=category)

    def cancel_all_orders_operator(self, request: CancelAllOrdersRequest) -> dict[str, Any]:
        self._require_kill_switch_feature()
        if not self._settings.live_broker_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_BROKER_ENABLED=false",
                retryable=False,
            )
        profile = self._endpoint_profile_for_settings()
        assert_write_capability(profile, "cancel_all")
        product_type = str(request.product_type or self._settings.product_type)
        margin_coin = str(request.margin_coin or self._settings.effective_margin_coin)
        cancel_all_path = str(profile.private_cancel_all_orders_path or "").strip()
        body = self._build_cancel_all_exchange_body(
            profile=profile,
            product_type=product_type,
            margin_coin=margin_coin,
        )
        response = self._call_private(
            internal_order_id=str(uuid4()),
            action="cancel_all",
            request_path=cancel_all_path,
            request_json=body,
            call=lambda: self._private.cancel_all_orders(
                body, priority=True, request_path=cancel_all_path
            ),
            client_oid=None,
            exchange_order_id=None,
        )
        local = self._cancel_matching_local_orders(
            scope="service",
            scope_key=_SERVICE_SCOPE_KEY,
            source=request.source,
            reason=request.reason,
            symbol=None,
            product_type=product_type,
            internal_order_id=None,
        )
        self._record_audit(
            category="emergency_cancel_all",
            action="operator_cancel_all",
            severity="critical",
            scope="service",
            scope_key=_SERVICE_SCOPE_KEY,
            source=request.source,
            internal_order_id=None,
            symbol=None,
            details={
                "reason": request.reason,
                "note": request.note,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "exchange": self._response_to_dict(response),
                "local": local,
            },
        )
        self._publish_safety_alert(
            alert_key="live-broker:operator:cancel-all",
            severity="critical",
            title="live-broker operator cancel-all",
            message=f"Cancel-All ausgefuehrt ({product_type}/{margin_coin})",
            details={
                "reason": request.reason,
                "source": request.source,
                "exchange": self._response_to_dict(response),
                "local_cancel_count": local.get("count"),
            },
        )
        return {"ok": True, "exchange": self._response_to_dict(response), "local": local}

    def release_safety_latch(self, request: SafetyLatchReleaseRequest) -> dict[str, Any]:
        if not self._repo.safety_latch_is_active():
            return {"ok": True, "idempotent": True}
        self._record_audit(
            category="safety_latch",
            action="release",
            severity="info",
            scope="service",
            scope_key="reconcile",
            source=request.source,
            internal_order_id=None,
            symbol=None,
            details={"reason": request.reason, "note": request.note},
        )
        self._publish_safety_alert(
            alert_key="live-broker:safety-latch:released",
            severity="info",
            title="live-broker safety latch released",
            message="Operator hat Safety-Latch geloest — Live-Fire wieder moeglich sofern uebrige Gates passen.",
            details={"reason": request.reason, "source": request.source},
        )
        return {"ok": True}

    def arm_kill_switch(self, request: KillSwitchRequest) -> dict[str, Any]:
        self._require_kill_switch_feature()
        scope, scope_key, symbol, product_type, margin_coin, internal_order_id = (
            self._resolve_kill_switch_scope(request)
        )
        existing = self._matching_kill_switch(scope, scope_key)
        if existing is not None:
            return {"ok": True, "idempotent": True, "item": existing, "auto_cancel": None}
        event = self._repo.record_kill_switch_event(
            {
                "scope": scope,
                "scope_key": scope_key,
                "event_type": "arm",
                "is_active": True,
                "source": request.source,
                "reason": request.reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
                "details_json": {"note": request.note},
            }
        )
        self._record_audit(
            category="kill_switch",
            action="arm",
            severity="critical" if scope in ("service", "account") else "warn",
            scope=scope,
            scope_key=scope_key,
            source=request.source,
            internal_order_id=internal_order_id,
            symbol=symbol,
            details={
                "reason": request.reason,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "note": request.note,
            },
        )
        self._publish_safety_alert(
            alert_key=f"live-broker:kill-switch:{scope}:{scope_key}:armed",
            severity="critical" if scope in ("service", "account") else "warn",
            title="live-broker kill switch armed",
            message=f"Kill switch aktiv: scope={scope} scope_key={scope_key}",
            details={
                "scope": scope,
                "scope_key": scope_key,
                "reason": request.reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
            },
        )
        auto_cancel = None
        try:
            if scope in ("service", "account"):
                auto_cancel = self._cancel_all_orders_for_scope(
                    scope=scope,
                    scope_key=scope_key,
                    source=request.source,
                    reason=request.reason,
                    symbol=symbol,
                    product_type=product_type,
                    margin_coin=margin_coin,
                    internal_order_id=internal_order_id,
                )
            elif scope == "trade" and internal_order_id is not None:
                auto_cancel = self._cancel_matching_local_orders(
                    scope=scope,
                    scope_key=scope_key,
                    source=request.source,
                    reason=request.reason,
                    symbol=symbol,
                    product_type=product_type,
                    internal_order_id=internal_order_id,
                )
        except Exception as exc:
            auto_cancel = {"ok": False, "error": str(exc)}
            self._record_audit(
                category="kill_switch",
                action="auto_cancel_failed",
                severity="critical",
                scope=scope,
                scope_key=scope_key,
                source=request.source,
                internal_order_id=internal_order_id,
                symbol=symbol,
                details={"reason": request.reason, "error": str(exc)},
            )
            self._publish_safety_alert(
                alert_key=f"live-broker:kill-switch:{scope}:{scope_key}:auto-cancel-failed",
                severity="critical",
                title="live-broker kill switch auto-cancel failed",
                message=f"Kill switch ist aktiv, Auto-Cancel schlug fehl fuer {scope_key}.",
                details={"scope": scope, "scope_key": scope_key, "reason": request.reason, "error": str(exc)},
            )
        return {"ok": True, "item": event, "auto_cancel": auto_cancel}

    def release_kill_switch(self, request: KillSwitchRequest) -> dict[str, Any]:
        self._require_kill_switch_feature()
        scope, scope_key, symbol, product_type, margin_coin, internal_order_id = (
            self._resolve_kill_switch_scope(request)
        )
        existing = self._matching_kill_switch(scope, scope_key)
        if existing is None:
            return {"ok": True, "idempotent": True, "item": None}
        event = self._repo.record_kill_switch_event(
            {
                "scope": scope,
                "scope_key": scope_key,
                "event_type": "release",
                "is_active": False,
                "source": request.source,
                "reason": request.reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
                "details_json": {"note": request.note},
            }
        )
        self._record_audit(
            category="kill_switch",
            action="release",
            severity="info",
            scope=scope,
            scope_key=scope_key,
            source=request.source,
            internal_order_id=internal_order_id,
            symbol=symbol,
            details={"reason": request.reason},
        )
        self._publish_safety_alert(
            alert_key=f"live-broker:kill-switch:{scope}:{scope_key}:released",
            severity="info",
            title="live-broker kill switch released",
            message=f"Kill switch geloest: scope={scope} scope_key={scope_key}",
            details={
                "scope": scope,
                "scope_key": scope_key,
                "reason": request.reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
            },
        )
        return {"ok": True, "item": event}

    def emergency_flatten(self, request: EmergencyFlattenRequest) -> dict[str, Any]:
        self._require_emergency_flatten_allowed()
        internal_order_id = str(request.internal_order_id) if request.internal_order_id else None
        symbol = request.symbol
        product_type = request.product_type or self._settings.product_type
        margin_coin = request.margin_coin or self._settings.effective_margin_coin
        if internal_order_id is not None:
            existing = self._require_local_order(internal_order_id)
            symbol = symbol or str(existing.get("symbol") or "")
            product_type = str(existing.get("product_type") or product_type)
            margin_coin = str(existing.get("margin_coin") or margin_coin)
            internal_order_id = self._trade_root_internal_order_id(internal_order_id)
        if not symbol:
            raise BitgetRestError(
                classification="validation",
                message="Emergency flatten braucht symbol oder internal_order_id",
                retryable=False,
            )
        scope, scope_key = self._flatten_scope(request)
        kill_switch_active = self._matching_kill_switch(scope, scope_key) is not None
        resolved_order = self._resolve_flatten_order(
            symbol=symbol,
            side=request.side,
            size=request.size,
        )
        event = self._repo.record_kill_switch_event(
            {
                "scope": scope,
                "scope_key": scope_key,
                "event_type": "flatten_requested",
                "is_active": kill_switch_active,
                "source": request.source_service,
                "reason": request.reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
                "details_json": {
                    "cancel_open_orders": request.cancel_open_orders,
                    "note": request.note,
                    "resolved_order": resolved_order,
                },
            }
        )
        self._record_audit(
            category="emergency_flatten",
            action="requested",
            severity="critical",
            scope=scope,
            scope_key=scope_key,
            source=request.source_service,
            internal_order_id=internal_order_id,
            symbol=symbol,
            details={
                "reason": request.reason,
                "cancel_open_orders": request.cancel_open_orders,
                "resolved_order": resolved_order,
            },
        )
        self._publish_safety_alert(
            alert_key=f"live-broker:flatten:{scope}:{scope_key}:requested",
            severity="critical",
            title="live-broker emergency flatten requested",
            message=f"Emergency flatten angefordert fuer {symbol}",
            details={
                "scope": scope,
                "scope_key": scope_key,
                "reason": request.reason,
                "symbol": symbol,
                "internal_order_id": internal_order_id,
                "resolved_order": resolved_order,
            },
        )
        cancel_summary = None
        if request.cancel_open_orders:
            cancel_summary = self._cancel_open_orders_for_flatten(
                scope=scope,
                scope_key=scope_key,
                source=request.source_service,
                reason=request.reason,
                symbol=symbol,
                product_type=product_type,
                margin_coin=margin_coin,
                internal_order_id=internal_order_id,
            )
        if resolved_order is None:
            completed = self._repo.record_kill_switch_event(
                {
                    "scope": scope,
                    "scope_key": scope_key,
                    "event_type": "flatten_skipped_flat",
                    "is_active": kill_switch_active,
                    "source": request.source_service,
                    "reason": request.reason,
                    "symbol": symbol,
                    "product_type": product_type,
                    "margin_coin": margin_coin,
                    "internal_order_id": internal_order_id,
                    "details_json": {"cancel_summary": cancel_summary, "note": request.note},
                }
            )
            self._record_audit(
                category="emergency_flatten",
                action="already_flat",
                severity="warn",
                scope=scope,
                scope_key=scope_key,
                source=request.source_service,
                internal_order_id=internal_order_id,
                symbol=symbol,
                details={"reason": request.reason, "cancel_summary": cancel_summary},
            )
            self._publish_safety_alert(
                alert_key=f"live-broker:flatten:{scope}:{scope_key}:already-flat",
                severity="warn",
                title="live-broker emergency flatten skipped",
                message=f"Keine offene Position fuer {symbol} mehr vorhanden.",
                details={
                    "scope": scope,
                    "scope_key": scope_key,
                    "reason": request.reason,
                    "symbol": symbol,
                    "cancel_summary": cancel_summary,
                },
            )
            return {
                "ok": True,
                "event": event,
                "completed": completed,
                "cancel_summary": cancel_summary,
                "result": None,
                "flattened": False,
            }
        try:
            result = self.create_reduce_only_order(
                ReduceOnlyOrderRequest(
                    source_service="live-broker",
                    symbol=symbol,
                    product_type=product_type,
                    margin_mode=request.margin_mode,
                    margin_coin=margin_coin,
                    side=resolved_order["side"],
                    trade_side="close",
                    order_type="market",
                    size=resolved_order["size"],
                    note=request.note or f"emergency_flatten:{request.reason}",
                    trace={
                        **request.trace,
                        "safety_action": "emergency_flatten",
                        "reason": request.reason,
                        "resolved_order": resolved_order,
                    },
                ),
                priority=True,
                allow_safety_bypass=True,
            )
        except Exception as exc:
            self._repo.record_kill_switch_event(
                {
                    "scope": scope,
                    "scope_key": scope_key,
                    "event_type": "flatten_failed",
                    "is_active": kill_switch_active,
                    "source": request.source_service,
                    "reason": request.reason,
                    "symbol": symbol,
                    "product_type": product_type,
                    "margin_coin": margin_coin,
                    "internal_order_id": internal_order_id,
                    "details_json": {
                        "error": str(exc),
                        "cancel_summary": cancel_summary,
                        "resolved_order": resolved_order,
                    },
                }
            )
            self._record_audit(
                category="emergency_flatten",
                action="failed",
                severity="critical",
                scope=scope,
                scope_key=scope_key,
                source=request.source_service,
                internal_order_id=internal_order_id,
                symbol=symbol,
                details={
                    "reason": request.reason,
                    "error": str(exc),
                    "cancel_summary": cancel_summary,
                    "resolved_order": resolved_order,
                },
            )
            self._publish_safety_alert(
                alert_key=f"live-broker:flatten:{scope}:{scope_key}:failed",
                severity="critical",
                title="live-broker emergency flatten failed",
                message=f"Emergency flatten fehlgeschlagen fuer {symbol}",
                details={
                    "scope": scope,
                    "scope_key": scope_key,
                    "reason": request.reason,
                    "symbol": symbol,
                    "error": str(exc),
                },
            )
            raise
        completed = self._repo.record_kill_switch_event(
            {
                "scope": scope,
                "scope_key": scope_key,
                "event_type": "flatten_completed",
                "is_active": kill_switch_active,
                "source": request.source_service,
                "reason": request.reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
                "details_json": {
                    "cancel_summary": cancel_summary,
                    "result": result,
                    "resolved_order": resolved_order,
                },
            }
        )
        self._record_audit(
            category="emergency_flatten",
            action="completed",
            severity="critical",
            scope=scope,
            scope_key=scope_key,
            source=request.source_service,
            internal_order_id=internal_order_id,
            symbol=symbol,
            details={
                "reason": request.reason,
                "cancel_summary": cancel_summary,
                "result": result,
                "resolved_order": resolved_order,
            },
        )
        self._publish_safety_alert(
            alert_key=f"live-broker:flatten:{scope}:{scope_key}:completed",
            severity="warn",
            title="live-broker emergency flatten completed",
            message=f"Emergency flatten ausgefuehrt fuer {symbol}",
            details={
                "scope": scope,
                "scope_key": scope_key,
                "reason": request.reason,
                "symbol": symbol,
                "cancel_summary": cancel_summary,
                "resolved_order": resolved_order,
            },
        )
        return {
            "ok": True,
            "event": event,
            "completed": completed,
            "cancel_summary": cancel_summary,
            "result": result,
            "resolved_order": resolved_order,
            "flattened": True,
        }

    def run_order_timeouts(self) -> dict[str, Any]:
        timeout_sec = getattr(self._settings, "live_order_timeout_sec", 0)
        if timeout_sec <= 0:
            return {"ok": True, "checked": 0, "timed_out": 0, "items": []}
        now = datetime.now(timezone.utc)
        candidates = self._repo.list_active_orders(limit=_OPEN_ORDER_SCAN_LIMIT)
        timed_out: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for order in candidates:
            created_at = self._parse_ts(order.get("created_ts"))
            if created_at is None:
                continue
            age_sec = (now - created_at).total_seconds()
            if age_sec < timeout_sec:
                continue
            try:
                result = self.cancel_order(
                    OrderCancelRequest(
                        internal_order_id=UUID(str(order["internal_order_id"])),
                        symbol=order.get("symbol"),
                        product_type=order.get("product_type"),
                        margin_coin=order.get("margin_coin"),
                        trace={"timeout_sec": timeout_sec, "order_age_sec": round(age_sec, 3)},
                    ),
                    priority=True,
                )
                stored = self._mark_order_as_timed_out(
                    result["item"],
                    timeout_sec=timeout_sec,
                    age_sec=age_sec,
                )
                self._record_audit(
                    category="order_timeout",
                    action="cancel",
                    severity="warn",
                    scope="trade",
                    scope_key=f"order:{order['internal_order_id']}",
                    source="live-broker",
                    internal_order_id=str(order["internal_order_id"]),
                    symbol=order.get("symbol"),
                    details={"timeout_sec": timeout_sec, "order_age_sec": round(age_sec, 3)},
                )
                timed_out.append(stored)
            except Exception as exc:
                self._record_audit(
                    category="order_timeout",
                    action="cancel_failed",
                    severity="critical",
                    scope="trade",
                    scope_key=f"order:{order['internal_order_id']}",
                    source="live-broker",
                    internal_order_id=str(order["internal_order_id"]),
                    symbol=order.get("symbol"),
                    details={
                        "timeout_sec": timeout_sec,
                        "order_age_sec": round(age_sec, 3),
                        "error": str(exc),
                    },
                )
                errors.append(
                    {
                        "internal_order_id": str(order["internal_order_id"]),
                        "error": str(exc),
                    }
                )
        if errors:
            self._publish_safety_alert(
                alert_key="live-broker:order-timeout:failures",
                severity="critical",
                title="live-broker order timeout cancel failed",
                message=f"Mindestens ein Timeout-Cancel ist fehlgeschlagen ({len(errors)} Fehler).",
                details={"errors": errors, "timeout_sec": timeout_sec},
            )
        elif timed_out:
            self._publish_safety_alert(
                alert_key="live-broker:order-timeout:cancelled",
                severity="warn",
                title="live-broker order timeout cancelled stale orders",
                message=f"{len(timed_out)} Live-Order(s) wurden wegen Timeout gecancelt.",
                details={
                    "timeout_sec": timeout_sec,
                    "internal_order_ids": [
                        str(item.get("internal_order_id")) for item in timed_out
                    ],
                },
            )
        return {
            "ok": not errors,
            "checked": len(candidates),
            "timed_out": len(timed_out),
            "items": timed_out,
            "errors": errors,
        }

    def state_snapshot(self) -> dict[str, Any]:
        try:
            order_status_counts = self._repo.order_status_counts()
        except Exception as exc:
            order_status_counts = {"unavailable": 0}
            logger.warning("order status snapshot unavailable: %s", exc)
        try:
            active_kill_switches = self._repo.active_kill_switches()
        except Exception as exc:
            active_kill_switches = []
            logger.warning("kill switch snapshot unavailable: %s", exc)
        try:
            safety_latch_active = self._repo.safety_latch_is_active()
        except Exception as exc:
            safety_latch_active = False
            logger.warning("safety latch snapshot unavailable: %s", exc)
        return {
            "execution_mode": self._settings.execution_mode,
            "paper_path_active": self._settings.paper_path_active,
            "shadow_trade_enable": self._settings.shadow_trade_enable,
            "shadow_path_active": self._settings.shadow_path_active,
            "live_trade_enable": self._settings.live_trade_enable,
            "live_order_submission_enabled": self._settings.live_order_submission_enabled,
            "private_rest": self._private.state_snapshot(),
            "order_status_counts": order_status_counts,
            "kill_switch_enabled": self._settings.live_kill_switch_enabled,
            "risk_force_reduce_only_on_alert": self._settings.risk_force_reduce_only_on_alert,
            "order_timeout_sec": getattr(self._settings, "live_order_timeout_sec", 0),
            "active_kill_switches": active_kill_switches,
            "safety_latch_active": safety_latch_active,
            "live_order_replace_enabled": self._settings.live_order_replace_enabled,
            "live_safety_latch_on_reconcile_fail": self._settings.live_safety_latch_on_reconcile_fail,
            "predatory_passive_maker_default": self._settings.live_predatory_passive_maker_default,
            "passive_max_slippage_bps_default": self._settings.live_passive_max_slippage_bps_default,
            "passive_iceberg_slices_default": self._settings.live_passive_iceberg_slices_default,
        }

    def _can_submit_order(self, *, allow_safety_bypass: bool) -> bool:
        if self._settings.live_order_submission_enabled:
            return True
        return bool(
            allow_safety_bypass
            and self._settings.execution_mode == "live"
            and self._settings.live_broker_enabled
            and self._settings.live_kill_switch_enabled
        )

    def _require_kill_switch_feature(self) -> None:
        if not self._settings.live_kill_switch_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_KILL_SWITCH_ENABLED=false",
                retryable=False,
            )

    def _require_emergency_flatten_allowed(self) -> None:
        self._require_kill_switch_feature()
        if not self._settings.live_broker_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_BROKER_ENABLED=false",
                retryable=False,
            )
        if self._settings.execution_mode != "live":
            raise BitgetRestError(
                classification="service_disabled",
                message="Emergency flatten ist nur mit EXECUTION_MODE=live erlaubt",
                retryable=False,
            )

    def _resolve_kill_switch_scope(
        self,
        request: KillSwitchRequest,
    ) -> tuple[str, str, str | None, str | None, str | None, str | None]:
        if request.scope == "service":
            return (
                "service",
                _SERVICE_SCOPE_KEY,
                request.symbol,
                request.product_type or self._settings.product_type,
                request.margin_coin or self._settings.effective_margin_coin,
                str(request.internal_order_id) if request.internal_order_id else None,
            )
        if request.scope == "account":
            product_type = request.product_type or self._settings.product_type
            margin_coin = request.margin_coin or self._settings.effective_margin_coin
            return (
                "account",
                f"{product_type}:{margin_coin}",
                request.symbol,
                product_type,
                margin_coin,
                str(request.internal_order_id) if request.internal_order_id else None,
            )
        requested_internal_order_id = str(request.internal_order_id)
        existing = self._require_local_order(requested_internal_order_id)
        trade_root_internal_order_id = self._trade_root_internal_order_id(
            requested_internal_order_id
        )
        return (
            "trade",
            self._trade_scope_key(trade_root_internal_order_id),
            request.symbol or existing.get("symbol"),
            request.product_type or existing.get("product_type"),
            request.margin_coin or existing.get("margin_coin"),
            trade_root_internal_order_id,
        )

    def _flatten_scope(self, request: EmergencyFlattenRequest) -> tuple[str, str]:
        if request.internal_order_id is not None:
            return "trade", self._trade_scope_key(str(request.internal_order_id))
        product_type = request.product_type or self._settings.product_type
        margin_coin = request.margin_coin or self._settings.effective_margin_coin
        return "account", f"{product_type}:{margin_coin}"

    def _matching_kill_switch(self, scope: str, scope_key: str) -> dict[str, Any] | None:
        for item in self._repo.active_kill_switches():
            if item.get("scope") == scope and item.get("scope_key") == scope_key:
                return item
        return None

    def _matching_kill_switches_for_order(
        self,
        *,
        product_type: str,
        margin_coin: str,
        internal_order_id: str | None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        trade_scope_key = (
            self._trade_scope_key(internal_order_id)
            if internal_order_id is not None
            else None
        )
        for item in self._repo.active_kill_switches():
            scope = str(item.get("scope") or "")
            scope_key = str(item.get("scope_key") or "")
            if scope == "service" and scope_key == _SERVICE_SCOPE_KEY:
                out.append(item)
            elif scope == "account" and scope_key == f"{product_type}:{margin_coin}":
                out.append(item)
            elif scope == "trade" and trade_scope_key is not None and scope_key == trade_scope_key:
                out.append(item)
        return out

    def _assert_safety_latch_allows_submit(
        self,
        *,
        operation: str,
        reduce_only: bool,
        allow_safety_bypass: bool,
    ) -> None:
        if allow_safety_bypass:
            return
        if not self._repo.safety_latch_is_active():
            return
        if reduce_only:
            return
        self._record_audit(
            category="safety_latch",
            action="blocked_order_submit",
            severity="critical",
            scope="service",
            scope_key="reconcile",
            source="live-broker",
            internal_order_id=None,
            symbol=None,
            details={"operation": operation, "reduce_only": reduce_only},
        )
        raise BitgetRestError(
            classification="kill_switch",
            message=(
                f"Safety latch aktiv — {operation} blockiert "
                "(nur reduce_only bis operatorisches latch release)"
            ),
            retryable=False,
        )

    def _assert_kill_switch_allows_submit(
        self,
        *,
        operation: str,
        product_type: str,
        margin_coin: str,
        internal_order_id: str | None,
        reduce_only: bool,
        symbol: str,
    ) -> None:
        matches = self._matching_kill_switches_for_order(
            product_type=product_type,
            margin_coin=margin_coin,
            internal_order_id=internal_order_id,
        )
        if not matches:
            return
        if reduce_only and self._settings.risk_force_reduce_only_on_alert:
            return
        scopes = [f"{item['scope']}:{item['scope_key']}" for item in matches]
        self._record_audit(
            category="kill_switch",
            action="blocked_order_submit",
            severity="critical",
            scope=str(matches[0]["scope"]),
            scope_key=str(matches[0]["scope_key"]),
            source="live-broker",
            internal_order_id=internal_order_id,
            symbol=symbol,
            details={
                "operation": operation,
                "reduce_only": reduce_only,
                "matching_kill_switches": scopes,
            },
        )
        raise BitgetRestError(
            classification="kill_switch",
            message=(
                f"Kill switch blockiert {operation}: "
                f"matching={','.join(scopes)} reduce_only={reduce_only}"
            ),
            retryable=False,
        )

    def _assert_kill_switch_allows_existing_order(
        self,
        order: dict[str, Any],
        *,
        operation: str,
    ) -> None:
        self._assert_kill_switch_allows_submit(
            operation=operation,
            product_type=str(order.get("product_type") or self._settings.product_type),
            margin_coin=str(order.get("margin_coin") or self._settings.effective_margin_coin),
            internal_order_id=str(order.get("internal_order_id") or ""),
            reduce_only=bool(order.get("reduce_only")),
            symbol=str(order.get("symbol") or self._settings.symbol),
        )

    def _cancel_all_orders_for_scope(
        self,
        *,
        scope: str,
        scope_key: str,
        source: str,
        reason: str,
        symbol: str | None,
        product_type: str | None,
        margin_coin: str | None,
        internal_order_id: str | None,
    ) -> dict[str, Any]:
        profile = self._endpoint_profile_for_settings()
        path = str(profile.private_cancel_all_orders_path or "").strip()
        pt = str(product_type or self._settings.product_type)
        mc = str(margin_coin or self._settings.effective_margin_coin)
        exchange_part: dict[str, Any] | None = None
        if path:
            assert_write_capability(profile, "cancel_all")
            body = self._build_cancel_all_exchange_body(
                profile=profile,
                product_type=pt,
                margin_coin=mc,
            )
            response = self._call_private(
                internal_order_id=internal_order_id or str(uuid4()),
                action="cancel",
                request_path=path,
                request_json=body,
                call=lambda: self._private.cancel_all_orders(
                    body, priority=True, request_path=path
                ),
                client_oid=None,
                exchange_order_id=None,
            )
            exchange_part = self._response_to_dict(response)
        else:
            self._record_audit(
                category="kill_switch",
                action="exchange_cancel_all_skipped",
                severity="warn",
                scope=scope,
                scope_key=scope_key,
                source=source,
                internal_order_id=internal_order_id,
                symbol=symbol,
                details={
                    "reason": reason,
                    "note": "cancel_all_execution_disabled_for_family",
                    "market_family": profile.market_family,
                },
            )
        local = self._cancel_matching_local_orders(
            scope=scope,
            scope_key=scope_key,
            source=source,
            reason=reason,
            symbol=symbol,
            product_type=product_type,
            internal_order_id=internal_order_id,
        )
        event = self._repo.record_kill_switch_event(
            {
                "scope": scope,
                "scope_key": scope_key,
                "event_type": "auto_cancel",
                "is_active": True,
                "source": source,
                "reason": reason,
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin,
                "internal_order_id": internal_order_id,
                "details_json": {
                    "exchange": exchange_part,
                    "local": local,
                },
            }
        )
        self._record_audit(
            category="kill_switch",
            action="auto_cancel",
            severity="critical",
            scope=scope,
            scope_key=scope_key,
            source=source,
            internal_order_id=internal_order_id,
            symbol=symbol,
            details={"reason": reason, "exchange": exchange_part, "local": local},
        )
        return {"event": event, "exchange": exchange_part, "local": local}

    def _cancel_matching_local_orders(
        self,
        *,
        scope: str,
        scope_key: str,
        source: str,
        reason: str,
        symbol: str | None,
        product_type: str | None,
        internal_order_id: str | None,
    ) -> dict[str, Any]:
        matches = self._repo.list_active_orders(
            limit=_OPEN_ORDER_SCAN_LIMIT,
            symbol=symbol,
            product_type=product_type,
        )
        if scope == "trade" and internal_order_id is not None:
            trade_scope_key = self._trade_scope_key(internal_order_id)
            matches = [
                order
                for order in matches
                if self._trade_scope_key(str(order.get("internal_order_id") or "")) == trade_scope_key
            ]
        items: list[dict[str, Any]] = []
        for order in matches:
            try:
                result = self.cancel_order(
                    OrderCancelRequest(
                        internal_order_id=UUID(str(order["internal_order_id"])),
                        symbol=order.get("symbol"),
                        product_type=order.get("product_type"),
                        margin_coin=order.get("margin_coin"),
                        trace={"safety_reason": reason, "scope": scope, "scope_key": scope_key},
                    ),
                    priority=True,
                )
                items.append({"ok": True, "internal_order_id": order["internal_order_id"], "item": result["item"]})
            except Exception as exc:
                self._record_audit(
                    category="kill_switch",
                    action="auto_cancel_failed",
                    severity="critical",
                    scope=scope,
                    scope_key=scope_key,
                    source=source,
                    internal_order_id=str(order["internal_order_id"]),
                    symbol=order.get("symbol"),
                    details={"reason": reason, "error": str(exc)},
                )
                items.append({"ok": False, "internal_order_id": order["internal_order_id"], "error": str(exc)})
        return {"count": len(matches), "items": items}

    def _record_audit(
        self,
        *,
        category: str,
        action: str,
        severity: str,
        scope: str,
        scope_key: str,
        source: str,
        internal_order_id: str | None,
        symbol: str | None,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return self._repo.record_audit_trail(
            {
                "category": category,
                "action": action,
                "severity": severity,
                "scope": scope,
                "scope_key": scope_key,
                "source": source,
                "internal_order_id": internal_order_id,
                "symbol": symbol,
                "details_json": details,
            }
        )

    def _publish_safety_alert(
        self,
        *,
        alert_key: str,
        severity: str,
        title: str,
        message: str,
        details: dict[str, Any],
    ) -> None:
        if self._bus is None:
            return
        try:
            publish_system_alert(
                self._bus,
                alert_key=alert_key,
                severity=severity,
                title=title,
                message=message,
                details=details,
            )
        except Exception as exc:
            logger.warning("failed to publish safety alert: %s", exc)

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

    def _trade_scope_key(self, internal_order_id: str) -> str:
        return f"order:{self._trade_root_internal_order_id(internal_order_id)}"

    def _trade_root_internal_order_id(self, internal_order_id: str) -> str:
        current_id = str(internal_order_id).strip()
        if not current_id:
            return current_id
        visited = {current_id}
        while True:
            current = self._repo.get_order_by_internal_id(current_id)
            if current is None:
                return current_id
            parent_id = str(current.get("parent_internal_order_id") or "").strip()
            if not parent_id or parent_id in visited:
                return current_id
            visited.add(parent_id)
            current_id = parent_id

    def _resolve_flatten_order(
        self,
        *,
        symbol: str,
        side: str | None,
        size: str | None,
    ) -> dict[str, Any] | None:
        if side is not None and size is not None:
            return {"side": side, "size": size, "resolved_from": "request"}
        exchange_position = self._flatten_position_from_snapshots(symbol)
        if exchange_position is not None:
            return self._position_to_flatten_order(
                symbol=symbol,
                net_size=exchange_position,
                resolved_from="exchange_positions",
            )
        local_position = self._flatten_position_from_local_fills(symbol)
        if local_position is not None:
            return self._position_to_flatten_order(
                symbol=symbol,
                net_size=local_position,
                resolved_from="local_fills",
            )
        return None

    def _position_to_flatten_order(
        self,
        *,
        symbol: str,
        net_size: Decimal,
        resolved_from: str,
    ) -> dict[str, Any] | None:
        if net_size.copy_abs() == Decimal("0"):
            return None
        return {
            "symbol": symbol,
            "side": "sell" if net_size > 0 else "buy",
            "size": format(net_size.copy_abs(), "f"),
            "resolved_from": resolved_from,
        }

    def _flatten_position_from_snapshots(self, symbol: str) -> Decimal | None:
        if not hasattr(self._repo, "list_latest_exchange_snapshots"):
            return None
        try:
            snapshots = self._repo.list_latest_exchange_snapshots(  # type: ignore[attr-defined]
                "positions",
                symbol=symbol,
                limit=20,
            )
        except Exception:
            return None
        seen_position = False
        net_size = Decimal("0")
        for snapshot in snapshots:
            raw = snapshot.get("raw_data") or {}
            items = raw.get("items") if isinstance(raw, dict) else None
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_symbol = str(item.get("instId") or snapshot.get("symbol") or "").strip()
                if item_symbol and item_symbol != symbol:
                    continue
                total = self._to_decimal(item.get("total"))
                if total is None:
                    continue
                hold_side = str(item.get("holdSide") or "").strip().lower()
                seen_position = True
                if hold_side == "short":
                    net_size -= total
                else:
                    net_size += total
        if not seen_position:
            return None
        return net_size

    def _flatten_position_from_local_fills(self, symbol: str) -> Decimal | None:
        if not hasattr(self._repo, "list_recent_fills"):
            return None
        try:
            fills = self._repo.list_recent_fills(  # type: ignore[attr-defined]
                _OPEN_ORDER_SCAN_LIMIT,
                symbol=symbol,
            )
        except Exception:
            return None
        net_size = Decimal("0")
        seen_fill = False
        for fill in fills:
            side = str(fill.get("side") or "").strip().lower()
            raw = fill.get("raw_json") or {}
            trade_side = str(raw.get("tradeSide") or "").strip().lower()
            size = self._to_decimal(fill.get("size"))
            if size is None:
                continue
            seen_fill = True
            is_open = (
                "open" in trade_side
                or trade_side in {"buy_single", "sell_single"}
            )
            if is_open:
                net_size += size if side == "buy" else -size
            else:
                net_size += -size if side == "sell" else size
        if not seen_fill:
            return None
        return net_size

    def _cancel_open_orders_for_flatten(
        self,
        *,
        scope: str,
        scope_key: str,
        source: str,
        reason: str,
        symbol: str,
        product_type: str,
        margin_coin: str,
        internal_order_id: str | None,
    ) -> dict[str, Any]:
        if scope == "trade":
            return self._cancel_matching_local_orders(
                scope=scope,
                scope_key=scope_key,
                source=source,
                reason=reason,
                symbol=symbol,
                product_type=product_type,
                internal_order_id=internal_order_id,
            )
        try:
            body = {"productType": product_type, "marginCoin": margin_coin}
            response = self._call_private(
                internal_order_id=internal_order_id or str(uuid4()),
                action="cancel",
                request_path="/api/v2/mix/order/cancel-all-orders",
                request_json=body,
                call=lambda: self._private.cancel_all_orders(body, priority=True),
                client_oid=None,
                exchange_order_id=None,
            )
            local = self._cancel_matching_local_orders(
                scope=scope,
                scope_key=scope_key,
                source=source,
                reason=reason,
                symbol=symbol,
                product_type=product_type,
                internal_order_id=None,
            )
            self._record_audit(
                category="emergency_flatten",
                action="cancel_open_orders",
                severity="critical",
                scope=scope,
                scope_key=scope_key,
                source=source,
                internal_order_id=internal_order_id,
                symbol=symbol,
                details={
                    "reason": reason,
                    "exchange": self._response_to_dict(response),
                    "local": local,
                },
            )
            return {
                "ok": True,
                "exchange": self._response_to_dict(response),
                "local": local,
            }
        except Exception as exc:
            self._record_audit(
                category="emergency_flatten",
                action="cancel_open_orders_failed",
                severity="critical",
                scope=scope,
                scope_key=scope_key,
                source=source,
                internal_order_id=internal_order_id,
                symbol=symbol,
                details={"reason": reason, "error": str(exc)},
            )
            self._publish_safety_alert(
                alert_key=f"live-broker:flatten:{scope}:{scope_key}:cancel-open-orders-failed",
                severity="critical",
                title="live-broker emergency flatten cancel-open-orders failed",
                message=f"Open-Order-Cancel vor Emergency flatten schlug fehl fuer {symbol}",
                details={
                    "scope": scope,
                    "scope_key": scope_key,
                    "reason": reason,
                    "symbol": symbol,
                    "error": str(exc),
                },
            )
            return {"ok": False, "error": str(exc)}

    def _mark_order_as_timed_out(
        self,
        order: dict[str, Any],
        *,
        timeout_sec: int,
        age_sec: float,
    ) -> dict[str, Any]:
        return self._repo.upsert_order(
            {
                **order,
                "status": "timed_out",
                "last_action": "timeout_cancel",
                "trace_json": {
                    **(order.get("trace_json") or {}),
                    "timeout_sec": timeout_sec,
                    "order_age_sec": round(age_sec, 3),
                    "timed_out": True,
                },
            }
        )

    def _to_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _order_endpoint_profile(
        self,
        market_family: str,
        margin_account_mode: str | None,
    ) -> BitgetEndpointProfile:
        fam = str(market_family).lower()
        mode: MarginAccountMode = "cash"
        if fam == "margin":
            raw = (margin_account_mode or self._settings.margin_account_mode or "isolated").lower()
            mode = "crossed" if raw == "crossed" else "isolated"
        return endpoint_profile_for(fam, margin_account_mode=mode)

    def _endpoint_profile_for_settings(self) -> BitgetEndpointProfile:
        mf = str(self._settings.market_family)
        ma = (
            str(self._settings.margin_account_mode).lower()
            if mf.lower() == "margin"
            else None
        )
        return self._order_endpoint_profile(mf, ma)

    def _build_cancel_all_exchange_body(
        self,
        *,
        profile: BitgetEndpointProfile,
        product_type: str,
        margin_coin: str,
    ) -> dict[str, Any]:
        if profile.market_family == "futures":
            return {
                "productType": product_type,
                "marginCoin": margin_coin,
            }
        return {}

    def _append_execution_journal(
        self,
        *,
        phase: str,
        execution_decision_id: str | None,
        internal_order_id: str | None,
        details: dict[str, Any],
    ) -> None:
        try:
            safe_details = redact_nested_mapping(details, max_depth=4)
            self._repo.record_execution_journal(
                {
                    "phase": phase,
                    "execution_decision_id": execution_decision_id,
                    "internal_order_id": internal_order_id,
                    "details_json": safe_details,
                }
            )
        except Exception as exc:
            logger.warning(
                "execution journal append failed phase=%s err=%s",
                phase,
                exc,
            )

    def _assert_reconcile_snapshot_allows_submit(self, *, operation: str) -> None:
        if not self._settings.live_block_submit_on_reconcile_fail and not (
            self._settings.live_block_submit_on_reconcile_degraded
        ):
            return
        snap_fn = getattr(self._repo, "latest_reconcile_snapshot", None)
        if not callable(snap_fn):
            return
        snap = snap_fn()
        if not isinstance(snap, dict):
            return
        status = str(snap.get("status") or "ok").lower()
        if self._settings.live_block_submit_on_reconcile_fail and status == "fail":
            self._publish_safety_alert(
                alert_key="live-broker:execution-guard:reconcile_fail_block",
                severity="critical",
                title="live-broker submit blockiert (reconcile fail)",
                message=f"Operation {operation} abgelehnt: letzter Reconcile-Status=fail.",
                details={"operation": operation, "reconcile_snapshot": snap},
            )
            raise BitgetRestError(
                classification="service_disabled",
                message=f"reconcile_status_fail_blockiert_{operation}",
                retryable=False,
            )
        if self._settings.live_block_submit_on_reconcile_degraded and status == "degraded":
            self._publish_safety_alert(
                alert_key="live-broker:execution-guard:reconcile_degraded_block",
                severity="warn",
                title="live-broker submit blockiert (reconcile degraded)",
                message=f"Operation {operation} abgelehnt: letzter Reconcile-Status=degraded.",
                details={"operation": operation, "reconcile_snapshot": snap},
            )
            raise BitgetRestError(
                classification="service_disabled",
                message=f"reconcile_status_degraded_blockiert_{operation}",
                retryable=False,
            )

    def _assert_public_exchange_probe(self, *, operation: str) -> None:
        if not self._settings.live_probe_public_api_before_order_submit:
            return
        if self._exchange_client is None:
            return
        probe = self._exchange_client.probe_exchange()
        if self._settings.live_require_exchange_health and not probe.get("public_api_ok"):
            self._publish_safety_alert(
                alert_key="live-broker:execution-guard:public_probe_fail",
                severity="critical",
                title="live-broker public probe failed vor submit",
                message=f"Operation {operation}: Bitget Public API nicht erreichbar.",
                details={"operation": operation, "probe": probe},
            )
            raise BitgetRestError(
                classification="service_disabled",
                message="public_exchange_probe_failed_before_submit",
                retryable=False,
            )

    def _assert_submit_runtime_gates(self, *, allow_safety_bypass: bool, operation: str) -> None:
        if allow_safety_bypass:
            return
        if not self._settings.live_order_submission_enabled:
            return
        self._assert_modul_mate_policy_allows_exchange_submit(
            allow_safety_bypass=allow_safety_bypass
        )
        self._assert_reconcile_snapshot_allows_submit(operation=operation)
        self._assert_public_exchange_probe(operation=operation)

    def _exchange_net_position_base(self, symbol: str) -> Decimal | None:
        return self._flatten_position_from_snapshots(symbol)

    def _maybe_arm_safety_latch_duplicate_recovery_failed(
        self,
        *,
        internal_order_id: str,
        client_oid: str,
        symbol: str,
    ) -> None:
        if not self._settings.live_safety_latch_on_duplicate_recovery_fail:
            return
        if self._repo.safety_latch_is_active():
            return
        self._repo.record_audit_trail(
            {
                "category": "safety_latch",
                "action": "arm",
                "severity": "critical",
                "scope": "service",
                "scope_key": "duplicate_recovery",
                "source": "live-broker",
                "internal_order_id": internal_order_id,
                "symbol": symbol,
                "details_json": {
                    "reason": "duplicate_exchange_response_order_recovery_failed",
                    "client_oid": client_oid,
                },
            }
        )
        self._publish_safety_alert(
            alert_key="live-broker:safety-latch:armed:duplicate_recovery",
            severity="critical",
            title="live-broker safety latch — duplicate recovery failed",
            message=(
                "Bitget meldete duplicate, lokale Order fehlt und Remote-Detail nicht lesbar — "
                "Safety-Latch gesetzt (LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL)."
            ),
            details={"internal_order_id": internal_order_id, "client_oid": client_oid, "symbol": symbol},
        )

    def _evaluate_post_preflight_execution_guards(
        self,
        *,
        request: OrderCreateRequest,
        body: dict[str, Any],
        effective_family: str,
        margin_mode_for_profile: str | None,
        product_type: str,
        trace_merged: dict[str, Any],
    ) -> None:
        reasons: list[str] = []
        max_spread = self._settings.live_execution_max_spread_half_bps_market
        stop_raw = (
            body.get("presetStopLossPrice")
            or body.get("preset_stop_loss_price")
            or request.preset_stop_loss_price
        )
        min_dist = self._settings.live_preset_stop_min_distance_bps
        min_mult = self._settings.live_preset_stop_min_spread_mult
        need_snapshot = (request.order_type == "market" and max_spread is not None) or (
            stop_raw not in (None, "")
            and (min_dist is not None or min_mult is not None)
        )
        net = (
            self._exchange_net_position_base(request.symbol)
            if request.reduce_only
            else None
        )
        require_pos = (
            bool(request.reduce_only)
            and self._settings.live_require_exchange_position_for_reduce_only
            and self._settings.private_exchange_access_enabled
        )
        reasons.extend(
            reduce_only_position_consistency_reasons(
                reduce_only=bool(request.reduce_only),
                order_side=request.side,
                position_net_base=net,
                require_known_position=require_pos,
            )
        )
        snap: dict[str, Any] | None = None
        if need_snapshot:
            if self._exchange_client is None:
                reasons.append("execution_guards_require_exchange_client")
            else:
                try:
                    snap = self._exchange_client.get_market_snapshot_for_family(
                        request.symbol,
                        market_family=effective_family,
                        product_type=product_type if effective_family == "futures" else None,
                        margin_account_mode=margin_mode_for_profile,
                    )
                    trace_merged["execution_guard_market_snapshot"] = {
                        k: snap.get(k)
                        for k in (
                            "bid_price",
                            "ask_price",
                            "mark_price",
                            "last_price",
                            "request_time",
                        )
                    }
                except Exception as exc:
                    reasons.append(f"public_market_snapshot_failed:{str(exc)[:180]}")
        if snap and request.order_type == "market" and max_spread is not None:
            bid = self._to_decimal(snap.get("bid_price"))
            ask = self._to_decimal(snap.get("ask_price"))
            reasons.extend(
                market_spread_slippage_cap_reasons(
                    side=request.side,
                    bid=bid,
                    ask=ask,
                    max_spread_half_bps=Decimal(str(max_spread)),
                )
            )
        if snap and stop_raw not in (None, ""):
            stop_px = self._to_decimal(stop_raw)
            mark = self._to_decimal(snap.get("mark_price"))
            last = self._to_decimal(snap.get("last_price"))
            ref = mark if mark is not None and mark > 0 else last
            bid = self._to_decimal(snap.get("bid_price"))
            ask = self._to_decimal(snap.get("ask_price"))
            if ref is not None and ref > 0 and stop_px is not None:
                if min_dist is not None:
                    reasons.extend(
                        preset_stop_distance_floor_reasons(
                            stop_price=stop_px,
                            reference_price=ref,
                            min_distance_bps=Decimal(str(min_dist)),
                        )
                    )
                if min_mult is not None:
                    reasons.extend(
                        preset_stop_vs_spread_reasons(
                            stop_price=stop_px,
                            reference_price=ref,
                            bid=bid,
                            ask=ask,
                            min_stop_to_spread_mult=Decimal(str(min_mult)),
                        )
                    )
        if reasons:
            detail = ",".join(reasons)
            self._publish_safety_alert(
                alert_key="live-broker:execution-guard:blocked",
                severity="critical",
                title="live-broker execution guard block",
                message=f"Order submit blockiert: {detail[:300]}",
                details={
                    "symbol": request.symbol,
                    "market_family": effective_family,
                    "reasons": reasons,
                },
            )
            self._record_audit(
                category="execution_guard",
                action="blocked_order_submit",
                severity="critical",
                scope="trade",
                scope_key=f"symbol:{request.symbol}",
                source="live-broker",
                internal_order_id=None,
                symbol=request.symbol,
                details={"reasons": reasons},
            )
            raise BitgetRestError(
                classification="validation",
                message="execution_guard_failed: " + detail,
                retryable=False,
            )

    def _assert_live_open_governance(
        self,
        request: OrderCreateRequest,
        *,
        opening_order: bool,
        allow_safety_bypass: bool,
    ) -> None:
        if allow_safety_bypass or not opening_order:
            return
        need_id = (
            self._settings.live_require_execution_binding
            or self._settings.live_require_operator_release_for_live_open
        )
        if not need_id:
            return
        if request.source_execution_decision_id is None:
            raise BitgetRestError(
                classification="validation",
                message=(
                    "Live-Open erfordert source_execution_decision_id "
                    "(LIVE_REQUIRE_EXECUTION_BINDING oder "
                    "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN)"
                ),
                retryable=False,
            )
        eid = str(request.source_execution_decision_id)
        row = self._repo.get_execution_decision(eid)
        if row is None:
            raise BitgetRestError(
                classification="validation",
                message=f"source_execution_decision_id unbekannt: {eid}",
                retryable=False,
            )
        if self._settings.live_require_execution_binding:
            if str(row.get("decision_action") or "") != "live_candidate_recorded":
                raise BitgetRestError(
                    classification="validation",
                    message=(
                        "execution binding: decision_action muss live_candidate_recorded sein "
                        f"(ist {row.get('decision_action')!r})"
                    ),
                    retryable=False,
                )
            if str(row.get("symbol") or "").upper() != request.symbol.upper():
                raise BitgetRestError(
                    classification="validation",
                    message="execution binding: symbol stimmt nicht mit Execution-Decision ueberein",
                    retryable=False,
                )
        if self._settings.live_require_operator_release_for_live_open:
            if self._repo.get_operator_release(eid) is None:
                raise BitgetRestError(
                    classification="validation",
                    message=(
                        "operator_release_required: POST "
                        f"/live-broker/executions/{eid}/operator-release "
                        "vor Live-Open-Order"
                    ),
                    retryable=False,
                )

    def _assert_catalog_order_capabilities(
        self,
        catalog_entry: Any,
        request: OrderCreateRequest,
        effective_family: str,
    ) -> None:
        if catalog_entry is None:
            return
        if bool(request.reduce_only) and not bool(catalog_entry.supports_reduce_only):
            raise BitgetRestError(
                classification="validation",
                message="Instrument unterstuetzt keine reduce-only Orders fuer diese Marktfamilie",
                retryable=False,
            )
        if effective_family == "spot" and request.trade_side == "open" and request.side == "sell":
            raise BitgetRestError(
                classification="validation",
                message="spot: open-short (sell+open) nicht unterstuetzt",
                retryable=False,
            )

    def _maybe_apply_passive_maker_rewrite(
        self,
        request: OrderCreateRequest,
        trace_merged: dict[str, Any],
        *,
        effective_family: str,
        product_type: str,
        margin_mode_for_profile: str | None,
        internal_order_id: UUID,
    ) -> OrderCreateRequest:
        """Market-Open (Futures) -> Post-Only Limit am Best-Bid/Ask; erste Iceberg-Tranche."""
        if request.reduce_only or effective_family != "futures":
            return request
        if request.order_type != "market":
            return request
        if not passive_maker_trace_enabled(
            settings_default=self._settings.live_predatory_passive_maker_default,
            trace=trace_merged,
        ):
            return request
        if self._exchange_client is None:
            return request
        params = passive_params_from_sources(
            settings_max_slippage_bps=self._settings.live_passive_max_slippage_bps_default,
            settings_slices=self._settings.live_passive_iceberg_slices_default,
            settings_imbalance_pause_ms=self._settings.live_passive_imbalance_pause_ms,
            settings_imbalance_threshold=self._settings.live_passive_imbalance_against_threshold,
            trace=trace_merged,
        )
        imb = coalesce_orderflow_imbalance(trace_merged)
        if orderflow_wall_against_side(
            side=request.side,
            orderflow_imbalance=imb,
            threshold=params.imbalance_against_threshold,
        ):
            raise BitgetRestError(
                classification="validation",
                message=(
                    "passive_maker_orderbook_wall: orderflow gegen unsere Seite "
                    f"(imbalance={imb}, threshold={params.imbalance_against_threshold}, "
                    f"suggested_pause_ms={params.imbalance_pause_ms})"
                ),
                retryable=True,
            )
        try:
            snap = self._exchange_client.get_market_snapshot_for_family(
                request.symbol,
                market_family=effective_family,
                product_type=product_type if effective_family == "futures" else None,
                margin_account_mode=margin_mode_for_profile,
            )
        except Exception as exc:
            raise BitgetRestError(
                classification="validation",
                message=f"passive_maker_market_snapshot_failed:{str(exc)[:200]}",
                retryable=False,
            ) from exc
        bid = self._to_decimal(snap.get("bid_price"))
        ask = self._to_decimal(snap.get("ask_price"))
        if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
            raise BitgetRestError(
                classification="validation",
                message="passive_maker_invalid_bid_ask_snapshot",
                retryable=False,
            )
        total = self._to_decimal(request.size)
        if total is None or total <= 0:
            return request
        seed = hash((str(trace_merged.get("correlation_id") or ""), str(internal_order_id))) % (2**32)
        rng = random.Random(seed)
        slices = plan_iceberg_sizes(total, params.iceberg_slices, rng)
        first = slices[0]
        px = passive_limit_price(side=request.side, bid=bid, ask=ask)
        anchor_s = format(px, "f")
        prev_pm = trace_merged.get("predatory_passive_maker")
        prev_d = dict(prev_pm) if isinstance(prev_pm, dict) else {}
        trace_merged["predatory_passive_maker"] = {
            **prev_d,
            "enabled": True,
            "rewritten_from": "market",
            "iceberg_planned_sizes": [format(s, "f") for s in slices],
            "iceberg_slice_index": 0,
            "passive_anchor_price": anchor_s,
            "max_slippage_bps": params.max_slippage_bps,
            "iceberg_slices": params.iceberg_slices,
        }
        trace_merged["passive_anchor_price"] = anchor_s
        trace_merged["passive_maker_fee_target_maker_ratio_0_1"] = 0.9
        return request.model_copy(
            update={
                "order_type": "limit",
                "force": "post_only",
                "price": anchor_s,
                "size": format(first, "f"),
            }
        )

    def _create_order(
        self,
        request: OrderCreateRequest,
        *,
        action: str,
        action_tag: str,
        priority: bool,
        allow_safety_bypass: bool,
    ) -> dict[str, Any]:
        if not self._can_submit_order(allow_safety_bypass=allow_safety_bypass):
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_TRADE_ENABLE=false",
                retryable=False,
            )
        self._assert_safety_latch_allows_submit(
            operation=action,
            reduce_only=bool(request.reduce_only),
            allow_safety_bypass=allow_safety_bypass,
        )
        self._assert_submit_runtime_gates(
            allow_safety_bypass=allow_safety_bypass,
            operation=action,
        )
        self._assert_prepaid_allows_opening_order(
            request, allow_safety_bypass=allow_safety_bypass
        )
        internal_order_id = request.internal_order_id or uuid4()
        existing = self._repo.get_order_by_internal_id(str(internal_order_id))
        if existing is not None:
            return {"ok": True, "idempotent": True, "item": existing}
        trace_merged: dict[str, Any] = {**request.trace}
        if request.correlation_id:
            trace_merged.setdefault("correlation_id", request.correlation_id)
        catalog_entry = None
        metadata = None
        if self._catalog is not None:
            try:
                family = str(request.market_family or self._settings.market_family)
                catalog_entry = self._catalog.resolve_for_trading(
                    symbol=request.symbol,
                    market_family=family,
                    product_type=(
                        request.product_type or self._settings.product_type
                        if family == "futures"
                        else None
                    ),
                    margin_account_mode=str(
                        request.margin_account_mode or self._settings.margin_account_mode
                    )
                    if family == "margin"
                    else None,
                    refresh_if_missing=False,
                )
            except UnknownInstrumentError as exc:
                raise BitgetRestError(
                    classification="validation",
                    message=str(exc),
                    retryable=False,
                ) from exc
        if self._metadata_service is not None:
            try:
                family = str(request.market_family or self._settings.market_family)
                metadata = self._metadata_service.resolve_for_trading(
                    symbol=request.symbol,
                    market_family=family,
                    product_type=(
                        request.product_type or self._settings.product_type
                        if family == "futures"
                        else None
                    ),
                    margin_account_mode=(
                        str(request.margin_account_mode or self._settings.margin_account_mode)
                        if family == "margin"
                        else None
                    ),
                    refresh_if_missing=False,
                )
            except UnknownInstrumentError as exc:
                raise BitgetRestError(
                    classification="validation",
                    message=str(exc),
                    retryable=False,
                ) from exc
        effective_family = str(
            request.market_family
            or (catalog_entry.market_family if catalog_entry is not None else None)
            or self._settings.market_family
        ).lower()
        margin_mode_for_profile: str | None = None
        if effective_family == "margin":
            margin_mode_for_profile = str(
                request.margin_account_mode
                or (catalog_entry.margin_account_mode if catalog_entry is not None else None)
                or self._settings.margin_account_mode
            ).lower()
        profile = self._order_endpoint_profile(effective_family, margin_mode_for_profile)
        assert_write_capability(
            profile,
            "reduce_only" if request.reduce_only else "order_create",
        )
        if effective_family == "futures":
            product_type = (
                request.product_type
                or (catalog_entry.product_type if catalog_entry is not None else None)
                or self._settings.product_type
            )
        else:
            product_type = (
                request.product_type
                or (catalog_entry.product_type if catalog_entry is not None else None)
                or ("SPOT" if effective_family == "spot" else "MARGIN")
            )
        margin_coin = (
            request.margin_coin
            or (catalog_entry.margin_coin if catalog_entry is not None else None)
            or self._settings.effective_margin_coin
        )
        if not str(margin_coin or "").strip():
            margin_coin = "USDT"
        self._assert_catalog_order_capabilities(catalog_entry, request, effective_family)
        self._assert_live_open_governance(
            request,
            opening_order=not bool(request.reduce_only),
            allow_safety_bypass=allow_safety_bypass,
        )
        request = self._maybe_apply_passive_maker_rewrite(
            request,
            trace_merged,
            effective_family=effective_family,
            product_type=product_type,
            margin_mode_for_profile=margin_mode_for_profile,
            internal_order_id=internal_order_id,
        )
        self._assert_kill_switch_allows_submit(
            operation=action,
            product_type=product_type,
            margin_coin=margin_coin,
            internal_order_id=str(internal_order_id),
            reduce_only=bool(request.reduce_only),
            symbol=request.symbol,
        )
        client_oid = client_oid_for_internal_order(
            self._settings.order_idempotency_prefix,
            action_tag=action_tag,
            internal_order_id=internal_order_id,
        )
        trace_merged["client_submit_correlation_id"] = str(uuid4())
        trace_merged["effective_market_family"] = effective_family
        body = self._build_create_order_body(
            request=request,
            client_oid=client_oid,
            product_type=product_type,
            margin_coin=margin_coin,
            trace_merged=trace_merged,
            metadata=metadata,
            market_family=effective_family,
            endpoint_profile=profile,
        )
        place_path = profile.private_place_order_path or "/api/v2/mix/order/place-order"
        if metadata is not None:
            quote_size_order = (
                effective_family in {"spot", "margin"}
                and request.order_type == "market"
                and request.side == "buy"
            )
            meta_age = int(self._settings.live_preflight_max_catalog_metadata_age_sec)
            preflight = self._metadata_service.preflight_order(
                metadata=metadata,
                side=request.side,
                order_type=request.order_type,
                size=body.get("size") or body.get("baseSize") or body.get("quoteSize"),
                price=body.get("price"),
                reduce_only=bool(request.reduce_only),
                quote_size_order=quote_size_order,
                max_metadata_age_sec=meta_age if meta_age > 0 else None,
                account_margin_coin=margin_coin,
            )
            if not preflight.valid:
                raise BitgetRestError(
                    classification="validation",
                    message="instrument metadata preflight failed: " + ",".join(preflight.reasons),
                    retryable=False,
                )
            trace_merged["instrument_metadata"] = preflight.metadata.model_dump(mode="json")
            trace_merged["instrument_metadata_snapshot_id"] = preflight.metadata.snapshot_id
            trace_merged["instrument_preflight_notional_quote"] = preflight.computed_notional_quote
            if body.get("price") is not None and preflight.normalized_price is not None:
                body["price"] = preflight.normalized_price
            size_key = "size" if "size" in body else ("baseSize" if "baseSize" in body else "quoteSize")
            body[size_key] = preflight.normalized_size
        self._evaluate_post_preflight_execution_guards(
            request=request,
            body=body,
            effective_family=effective_family,
            margin_mode_for_profile=margin_mode_for_profile,
            product_type=product_type,
            trace_merged=trace_merged,
        )
        exit_plan_preview = None
        if self._exit_service is not None:
            request_for_preview = request.model_copy(update={"trace": trace_merged})
            exit_plan_preview = self._exit_service.preview_order_exit_plan(
                internal_order_id=str(internal_order_id),
                request=request_for_preview,
            )
        self._append_execution_journal(
            phase="order_submit",
            execution_decision_id=(
                str(request.source_execution_decision_id)
                if request.source_execution_decision_id
                else None
            ),
            internal_order_id=str(internal_order_id),
            details={
                "action": action,
                "symbol": request.symbol,
                "market_family": effective_family,
                "request_path": place_path,
            },
        )
        try:
            response = self._call_private(
                internal_order_id=str(internal_order_id),
                action=action,
                request_path=place_path,
                request_json=body,
                call=lambda: self._private.place_order(
                    body, priority=priority, request_path=place_path
                ),
                client_oid=client_oid,
                exchange_order_id=None,
            )
        except BitgetRestError as exc:
            if exc.classification == "duplicate":
                recovered = self._repo.get_order_by_client_oid(client_oid)
                if recovered is not None:
                    return {"ok": True, "idempotent": True, "item": recovered}
                detail = self._query_remote_detail(
                    symbol=request.symbol,
                    product_type=product_type,
                    client_oid=client_oid,
                    market_family=effective_family,
                    margin_account_mode=margin_mode_for_profile,
                )
                if detail is not None:
                    stored = self._repo.upsert_order(
                        {
                            "internal_order_id": str(internal_order_id),
                            "parent_internal_order_id": None,
                            "source_service": request.source_service,
                            "symbol": request.symbol,
                            "product_type": product_type,
                            "margin_mode": request.margin_mode,
                            "margin_coin": margin_coin,
                            "market_family": effective_family,
                            "margin_account_mode": (
                                margin_mode_for_profile if effective_family == "margin" else None
                            ),
                            "source_execution_decision_id": (
                                str(request.source_execution_decision_id)
                                if request.source_execution_decision_id
                                else None
                            ),
                            "side": request.side,
                            "trade_side": request.trade_side,
                            "order_type": request.order_type,
                            "force": request.force or ("gtc" if request.order_type == "limit" else None),
                            "reduce_only": request.reduce_only,
                            "size": request.size,
                            "price": request.price,
                            "note": request.note,
                            "client_oid": client_oid,
                            "exchange_order_id": self._extract_exchange_order_id({}, detail),
                            "status": self._extract_order_state(detail) or "submitted",
                            "last_action": action,
                            "last_http_status": detail.http_status,
                            "last_exchange_code": str(detail.payload.get("code") or ""),
                            "last_exchange_msg": str(detail.payload.get("msg") or ""),
                            "last_response_json": detail.payload,
                            "trace_json": trace_merged,
                        }
                    )
                    return {
                        "ok": True,
                        "idempotent": True,
                        "item": stored,
                        "detail": self._response_to_dict(detail),
                    }
                self._maybe_arm_safety_latch_duplicate_recovery_failed(
                    internal_order_id=str(internal_order_id),
                    client_oid=client_oid,
                    symbol=request.symbol,
                )
            self._repo.upsert_order(
                {
                    "internal_order_id": str(internal_order_id),
                    "parent_internal_order_id": None,
                    "source_service": request.source_service,
                    "symbol": request.symbol,
                    "product_type": product_type,
                    "margin_mode": request.margin_mode,
                    "margin_coin": margin_coin,
                    "market_family": effective_family,
                    "margin_account_mode": (
                        margin_mode_for_profile if effective_family == "margin" else None
                    ),
                    "source_execution_decision_id": (
                        str(request.source_execution_decision_id)
                        if request.source_execution_decision_id
                        else None
                    ),
                    "side": request.side,
                    "trade_side": request.trade_side,
                    "order_type": request.order_type,
                    "force": request.force or ("gtc" if request.order_type == "limit" else None),
                    "reduce_only": request.reduce_only,
                    "size": request.size,
                    "price": request.price,
                    "note": request.note,
                    "client_oid": client_oid,
                    "exchange_order_id": None,
                    "status": "error",
                    "last_action": action,
                    "last_http_status": exc.http_status,
                    "last_exchange_code": exc.exchange_code,
                    "last_exchange_msg": exc.exchange_msg or str(exc),
                    "last_response_json": exc.to_dict(),
                    "trace_json": trace_merged,
                }
            )
            raise

        detail = None
        exchange_order_id = self._extract_exchange_order_id(response.payload, None)
        if exchange_order_id is None:
            detail = self._query_remote_detail(
                symbol=request.symbol,
                product_type=product_type,
                client_oid=client_oid,
                market_family=effective_family,
                margin_account_mode=margin_mode_for_profile,
            )
            exchange_order_id = self._extract_exchange_order_id(response.payload, detail)
        stored = self._repo.upsert_order(
            {
                "internal_order_id": str(internal_order_id),
                "parent_internal_order_id": None,
                "source_service": request.source_service,
                "symbol": request.symbol,
                "product_type": product_type,
                "margin_mode": request.margin_mode,
                "margin_coin": margin_coin,
                "market_family": effective_family,
                "margin_account_mode": (
                    margin_mode_for_profile if effective_family == "margin" else None
                ),
                "source_execution_decision_id": (
                    str(request.source_execution_decision_id)
                    if request.source_execution_decision_id
                    else None
                ),
                "side": request.side,
                "trade_side": request.trade_side,
                "order_type": request.order_type,
                "force": request.force or ("gtc" if request.order_type == "limit" else None),
                "reduce_only": request.reduce_only,
                "size": request.size,
                "price": request.price,
                "note": request.note,
                "client_oid": client_oid,
                "exchange_order_id": exchange_order_id,
                "status": self._extract_order_state(detail) or "submitted",
                "last_action": action,
                "last_http_status": response.http_status,
                "last_exchange_code": str(response.payload.get("code") or ""),
                "last_exchange_msg": str(response.payload.get("msg") or ""),
                "last_response_json": detail.payload if detail is not None else response.payload,
                "trace_json": trace_merged,
            }
        )
        self._append_execution_journal(
            phase="order_exchange_ack",
            execution_decision_id=(
                str(request.source_execution_decision_id)
                if request.source_execution_decision_id
                else None
            ),
            internal_order_id=str(internal_order_id),
            details={
                "exchange_order_id": exchange_order_id,
                "http_status": response.http_status,
                "market_family": effective_family,
            },
        )
        if self._exit_service is not None:
            self._exit_service.persist_order_exit_plan(order=stored, preview=exit_plan_preview)
        return {
            "ok": True,
            "idempotent": False,
            "item": stored,
            "exchange": self._response_to_dict(response),
            "detail": self._response_to_dict(detail) if detail is not None else None,
        }

    def _resolve_identity(
        self,
        internal_order_id: UUID | None,
        order_id: str | None,
        client_oid: str | None,
    ) -> dict[str, Any]:
        if internal_order_id is not None:
            return self._require_local_order(str(internal_order_id))
        if client_oid is not None:
            existing = self._repo.get_order_by_client_oid(client_oid)
            if existing is not None:
                return existing
        if order_id is not None:
            existing = self._repo.get_order_by_exchange_order_id(order_id)
            if existing is not None:
                return existing
        if client_oid is not None or order_id is not None:
            return {
                "internal_order_id": str(uuid4()),
                "parent_internal_order_id": None,
                "source_service": "manual",
                "margin_mode": "isolated",
                "margin_coin": None,
                "market_family": None,
                "margin_account_mode": None,
                "source_execution_decision_id": None,
                "side": None,
                "trade_side": None,
                "order_type": None,
                "force": None,
                "reduce_only": False,
                "size": None,
                "price": None,
                "note": "",
                "client_oid": client_oid,
                "exchange_order_id": order_id,
                "status": "remote_only",
                "trace_json": {},
            }
        raise BitgetRestError(
            classification="not_found",
            message="Kein lokal korrelierter Order-Datensatz fuer diese Anfrage gefunden",
            retryable=False,
        )

    def _require_local_order(self, internal_order_id: str) -> dict[str, Any]:
        existing = self._repo.get_order_by_internal_id(internal_order_id)
        if existing is None:
            raise BitgetRestError(
                classification="not_found",
                message=f"internal_order_id nicht gefunden: {internal_order_id}",
                retryable=False,
            )
        return existing

    def _call_private(
        self,
        *,
        internal_order_id: str,
        action: str,
        request_path: str,
        request_json: dict[str, Any],
        call,
        client_oid: str | None,
        exchange_order_id: str | None,
    ) -> BitgetRestResponse:
        try:
            response = call()
        except BitgetRestError as exc:
            self._repo.record_order_action(
                {
                    "internal_order_id": internal_order_id,
                    "action": action,
                    "request_path": request_path,
                    "client_oid": client_oid,
                    "exchange_order_id": exchange_order_id,
                    "http_status": exc.http_status,
                    "exchange_code": exc.exchange_code,
                    "exchange_msg": exc.exchange_msg or str(exc),
                    "retry_count": 0,
                    "request_json": request_json,
                    "response_json": exc.to_dict(),
                }
            )
            if exc.classification in _DEAD_LETTER_CLASSIFICATIONS:
                try:
                    self._repo.record_audit_trail(
                        {
                            "category": "exchange_write_dead_letter",
                            "action": action,
                            "severity": "critical",
                            "scope": "trade",
                            "scope_key": internal_order_id,
                            "source": "live-broker",
                            "internal_order_id": internal_order_id,
                            "symbol": request_json.get("symbol"),
                            "details_json": {
                                "request_path": request_path,
                                "request_json": request_json,
                                "client_oid": client_oid,
                                "error": exc.to_dict(),
                            },
                        }
                    )
                except Exception as audit_exc:
                    logger.warning("dead_letter audit failed: %s", audit_exc)
            raise
        self._repo.record_order_action(
            {
                "internal_order_id": internal_order_id,
                "action": action,
                "request_path": request_path,
                "client_oid": client_oid,
                "exchange_order_id": exchange_order_id or self._extract_exchange_order_id(response.payload, None),
                "http_status": response.http_status,
                "exchange_code": str(response.payload.get("code") or ""),
                "exchange_msg": str(response.payload.get("msg") or ""),
                "retry_count": max(0, response.attempts - 1),
                "request_json": request_json,
                "response_json": response.payload,
            }
        )
        return response

    def _query_remote_detail(
        self,
        *,
        symbol: str,
        product_type: str,
        client_oid: str,
        market_family: str | None = None,
        margin_account_mode: str | None = None,
    ) -> BitgetRestResponse | None:
        fam = str(market_family or self._settings.market_family).lower()
        profile = self._order_endpoint_profile(fam, margin_account_mode)
        detail_path = (
            profile.private_order_detail_path or profile.private_open_orders_path or ""
        ).strip()
        if not detail_path:
            return None
        try:
            return self._private.get_order_detail(
                params={
                    **self._build_query_params(
                        symbol=symbol, product_type=product_type, market_family=fam
                    ),
                    "clientOid": client_oid,
                },
                request_path=detail_path,
                market_family=fam,
            )
        except BitgetRestError as exc:
            if exc.classification == "not_found":
                return None
            raise

    def _build_cancel_body(
        self,
        *,
        symbol: str,
        product_type: str,
        margin_coin: str,
        market_family: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"symbol": symbol}
        if str(market_family).lower() == "futures":
            body["productType"] = product_type
            body["marginCoin"] = margin_coin
        return body

    def _build_query_params(
        self, *, symbol: str, product_type: str, market_family: str
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        family = str(market_family).lower()
        if family == "futures":
            params["symbol"] = symbol
            params["productType"] = product_type
        elif family == "margin":
            params["symbol"] = symbol
        if family == "margin":
            now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
            params.setdefault("startTime", str(now_ms - 90 * 24 * 60 * 60 * 1000))
            params.setdefault("endTime", str(now_ms))
            params.setdefault("limit", "1")
        return params

    def _build_create_order_body(
        self,
        *,
        request: OrderCreateRequest,
        client_oid: str,
        product_type: str,
        margin_coin: str,
        trace_merged: dict[str, Any],
        metadata: Any = None,
        market_family: str,
        endpoint_profile: BitgetEndpointProfile,
    ) -> dict[str, Any]:
        family = str(market_family).lower()
        body: dict[str, Any] = {
            "symbol": request.symbol,
            "side": request.side,
            "orderType": request.order_type,
            "clientOid": client_oid,
        }
        if request.order_type == "limit":
            body["price"] = request.price
            body["force"] = request.force or "gtc"
        if family == "futures":
            body.update(
                {
                    "productType": product_type,
                    "marginMode": request.margin_mode,
                    "marginCoin": margin_coin,
                    "size": request.size,
                    "reduceOnly": "YES" if request.reduce_only else "NO",
                }
            )
            if request.trade_side is not None:
                body["tradeSide"] = request.trade_side
            if request.preset_stop_surplus_price is not None:
                body["presetStopSurplusPrice"] = request.preset_stop_surplus_price
            if request.preset_stop_loss_price is not None:
                body["presetStopLossPrice"] = request.preset_stop_loss_price
            return body
        if family == "spot":
            body["size"] = request.size
            if request.preset_stop_surplus_price is not None:
                body["presetTakeProfitPrice"] = request.preset_stop_surplus_price
            if request.preset_stop_loss_price is not None:
                body["presetStopLossPrice"] = request.preset_stop_loss_price
            return body
        body["loanType"] = str(trace_merged.get("margin_loan_type") or self._settings.bitget_margin_loan_type)
        qty_key = (
            endpoint_profile.market_buy_quantity_field
            if request.order_type == "market" and request.side == "buy"
            else endpoint_profile.quantity_field
        )
        body[qty_key] = request.size
        return body

    def _extract_exchange_order_id(
        self,
        payload: dict[str, Any],
        detail: BitgetRestResponse | None,
    ) -> str | None:
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and data.get("orderId"):
            return str(data["orderId"])
        if detail is not None:
            detail_data = detail.payload.get("data") if isinstance(detail.payload, dict) else None
            if isinstance(detail_data, dict) and detail_data.get("orderId"):
                return str(detail_data["orderId"])
        return None

    def _extract_order_state(self, response: BitgetRestResponse | None) -> str | None:
        if response is None:
            return None
        data = response.payload.get("data") if isinstance(response.payload, dict) else None
        if not isinstance(data, dict):
            return None
        return str(data.get("state") or data.get("status") or "").strip() or None

    def _extract_reduce_only(self, data: dict[str, Any], fallback: Any) -> bool:
        if "reduceOnly" not in data:
            return bool(fallback)
        value = str(data.get("reduceOnly") or "").strip().lower()
        return value in ("yes", "true", "1")

    def _response_to_dict(self, response: BitgetRestResponse | None) -> dict[str, Any] | None:
        if response is None:
            return None
        return {
            "http_status": response.http_status,
            "request_path": response.request_path,
            "method": response.method,
            "query_string": response.query_string,
            "attempts": response.attempts,
            "payload": response.payload,
        }
