from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from shared_py.bitget.instruments import endpoint_profile_for

from live_broker.control_plane.capabilities import (
    CONTROL_PLANE_MATRIX_VERSION,
    capability_matrix_for_profile,
    assert_read_capability,
    assert_write_capability,
)
from live_broker.control_plane.models import (
    ControlPlaneReadHistoryRequest,
    ControlPlaneSetLeverageRequest,
)
from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings
    from live_broker.persistence.repo import LiveBrokerRepository

logger = logging.getLogger("live_broker.control_plane")


def _response_to_audit(resp: Any) -> dict[str, Any]:
    return {
        "http_status": resp.http_status,
        "request_path": resp.request_path,
        "method": resp.method,
        "attempts": resp.attempts,
        "payload": resp.payload,
    }


class BitgetControlPlaneService:
    """Einheitliche, policy-konforme Bitget-Zugriffe (Read/Write) mit Audit."""

    def __init__(
        self,
        settings: "LiveBrokerSettings",
        private: BitgetPrivateRestClient,
        repo: "LiveBrokerRepository",
    ) -> None:
        self._settings = settings
        self._private = private
        self._repo = repo

    def _runtime_profile(self) -> Any:
        mf = str(self._settings.market_family or "futures").lower()
        ma = (
            str(self._settings.margin_account_mode).lower()
            if mf == "margin"
            else "cash"
        )
        return endpoint_profile_for(mf, margin_account_mode=ma)  # type: ignore[arg-type]

    def matrix_payload(self) -> dict[str, Any]:
        profile = self._runtime_profile()
        return {
            "control_plane_matrix_version": CONTROL_PLANE_MATRIX_VERSION,
            "market_family": profile.market_family,
            "margin_account_mode": profile.default_margin_account_mode,
            "product_type": self._settings.product_type,
            "categories": capability_matrix_for_profile(profile),
        }

    def read_orders_history(self, body: ControlPlaneReadHistoryRequest) -> dict[str, Any]:
        profile = self._runtime_profile()
        assert_read_capability(profile, "order_history")
        params: dict[str, Any] = {"limit": str(body.limit)}
        if body.symbol:
            params["symbol"] = str(body.symbol).strip().upper()
        if body.start_time_ms:
            params["startTime"] = body.start_time_ms
        if body.end_time_ms:
            params["endTime"] = body.end_time_ms
        if str(profile.market_family).lower() == "futures" and self._settings.rest_product_type_param:
            params["productType"] = self._settings.product_type
        req_path = profile.private_order_history_path or ""
        snapshot = {
            "operation": "read_orders_history",
            "request_params": dict(params),
            "request_path": req_path,
            "operator_jti": body.operator_jti,
            "audit_note": body.audit_note,
        }
        try:
            resp = self._private.list_orders_history(
                params=params,
                priority=True,
                request_path=req_path,
                market_family=str(profile.market_family),
            )
        except BitgetRestError as exc:
            self._audit_exchange_action(
                category="control_plane_read",
                action="orders_history_failed",
                severity="warn",
                snapshot={**snapshot, "error": exc.to_dict()},
            )
            raise
        self._audit_exchange_action(
            category="control_plane_read",
            action="orders_history_ok",
            severity="info",
            snapshot={**snapshot, "response": _response_to_audit(resp)},
        )
        return {"ok": True, "exchange": _response_to_audit(resp)}

    def read_fill_history(self, body: ControlPlaneReadHistoryRequest) -> dict[str, Any]:
        profile = self._runtime_profile()
        assert_read_capability(profile, "fills")
        params: dict[str, Any] = {"limit": str(body.limit)}
        if body.symbol:
            params["symbol"] = str(body.symbol).strip().upper()
        if body.start_time_ms:
            params["startTime"] = body.start_time_ms
        if body.end_time_ms:
            params["endTime"] = body.end_time_ms
        if str(profile.market_family).lower() == "futures" and self._settings.rest_product_type_param:
            params["productType"] = self._settings.product_type
        if str(profile.market_family).lower() == "futures":
            params.setdefault("marginCoin", self._settings.effective_margin_coin)
        req_path = profile.private_fill_history_path or ""
        snapshot = {
            "operation": "read_fill_history",
            "request_params": dict(params),
            "request_path": req_path,
            "operator_jti": body.operator_jti,
            "audit_note": body.audit_note,
        }
        try:
            resp = self._private.list_fill_history(
                params=params,
                priority=True,
                request_path=req_path,
                market_family=str(profile.market_family),
            )
        except BitgetRestError as exc:
            self._audit_exchange_action(
                category="control_plane_read",
                action="fill_history_failed",
                severity="warn",
                snapshot={**snapshot, "error": exc.to_dict()},
            )
            raise
        self._audit_exchange_action(
            category="control_plane_read",
            action="fill_history_ok",
            severity="info",
            snapshot={**snapshot, "response": _response_to_audit(resp)},
        )
        return {"ok": True, "exchange": _response_to_audit(resp)}

    def set_leverage_operator(self, body: ControlPlaneSetLeverageRequest) -> dict[str, Any]:
        if not self._settings.live_order_submission_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_TRADE_ENABLE=false (kein Hebel-Setzen)",
                retryable=False,
            )
        profile = self._runtime_profile()
        assert_write_capability(profile, "leverage_config")
        symbol = str(body.symbol).strip().upper()
        product_type = str(body.product_type or self._settings.product_type)
        margin_coin = str(body.margin_coin or self._settings.effective_margin_coin)
        leverage_body: dict[str, Any] = {
            "symbol": symbol,
            "leverage": str(body.leverage).strip(),
            "productType": product_type,
            "marginCoin": margin_coin,
        }
        path = profile.private_set_leverage_path or ""
        snapshot = {
            "operation": "set_leverage",
            "request_body": leverage_body,
            "request_path": path,
            "operator_jti": body.operator_jti,
            "source": body.source,
            "reason": body.reason,
            "audit_note": body.audit_note,
        }
        try:
            resp = self._private.set_account_leverage(
                leverage_body, priority=False, request_path=path
            )
        except BitgetRestError as exc:
            self._dead_letter(snapshot, exc)
            self._audit_exchange_action(
                category="control_plane_write",
                action="set_leverage_failed",
                severity="critical",
                snapshot={**snapshot, "error": exc.to_dict()},
            )
            raise
        self._audit_exchange_action(
            category="control_plane_write",
            action="set_leverage_ok",
            severity="warn",
            snapshot={**snapshot, "response": _response_to_audit(resp)},
        )
        return {"ok": True, "exchange": _response_to_audit(resp)}

    def _audit_exchange_action(
        self,
        *,
        category: str,
        action: str,
        severity: str,
        snapshot: dict[str, Any],
    ) -> None:
        try:
            self._repo.record_audit_trail(
                {
                    "category": category,
                    "action": action,
                    "severity": severity,
                    "scope": "service",
                    "scope_key": "bitget_control_plane",
                    "source": "live-broker",
                    "internal_order_id": None,
                    "symbol": snapshot.get("request_body", {}).get("symbol")
                    or snapshot.get("request_params", {}).get("symbol"),
                    "details_json": snapshot,
                }
            )
        except Exception as exc:
            logger.warning("control_plane audit_trail failed: %s", exc)

    def _dead_letter(self, request_snapshot: dict[str, Any], exc: BitgetRestError) -> None:
        if exc.retryable:
            return
        try:
            self._repo.record_audit_trail(
                {
                    "category": "exchange_write_dead_letter",
                    "action": str(request_snapshot.get("operation") or "unknown"),
                    "severity": "critical",
                    "scope": "service",
                    "scope_key": "bitget_control_plane",
                    "source": "live-broker",
                    "internal_order_id": None,
                    "symbol": request_snapshot.get("request_body", {}).get("symbol"),
                    "details_json": {
                        "request_snapshot": request_snapshot,
                        "error": exc.to_dict(),
                        "operator_jti": request_snapshot.get("operator_jti"),
                    },
                }
            )
        except Exception as dl_exc:
            logger.warning("control_plane dead_letter audit failed: %s", dl_exc)
