from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from live_broker.execution.models import (
    ExecutionIntentRequest,
    OperatorReleasePostBody,
)
from live_broker.control_plane.models import (
    ControlPlaneReadHistoryRequest,
    ControlPlaneSetLeverageRequest,
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
from live_broker.private_rest import BitgetRestError
from shared_py.service_auth import InternalServiceAuthContext, build_internal_service_dependency


def _clamp_limit(limit: int, *, default: int = 20, cap: int = 200) -> int:
    return max(1, min(cap, int(limit or default)))


def build_ops_router(runtime) -> APIRouter:
    router = APIRouter(prefix="/live-broker", tags=["live-broker"])
    require_internal = build_internal_service_dependency(runtime.settings)

    @router.get("/runtime")
    def runtime_view(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return runtime.runtime_payload()

    @router.get("/decisions/recent")
    def recent_decisions(
        limit: int = 20,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {
            "items": runtime.execution_service.list_recent_decisions(_clamp_limit(limit)),
        }

    @router.get("/reference/paper")
    def recent_paper_reference(
        limit: int = 20,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {
            "items": runtime.execution_service.list_recent_paper_reference(
                _clamp_limit(limit)
            ),
        }

    @router.get("/reconcile/latest")
    def latest_reconcile(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {"item": runtime.reconcile_service.latest_snapshot()}

    @router.post("/executions/evaluate")
    def evaluate_execution(
        body: ExecutionIntentRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return runtime.execution_service.evaluate_intent(body)

    @router.get("/executions/{execution_id}/telegram-summary")
    def execution_telegram_summary(
        execution_id: UUID,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return runtime.execution_service.telegram_operator_release_summary(str(execution_id))

    @router.post("/executions/{execution_id}/operator-release")
    def operator_release_execution(
        execution_id: UUID,
        body: OperatorReleasePostBody | None = None,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        eff = body or OperatorReleasePostBody()
        return _wrap_bitget_error(
            lambda: runtime.execution_service.record_operator_release(
                str(execution_id),
                source=eff.source,
                details=eff.audit,
            )
        )

    @router.get("/executions/{execution_id}/journal")
    def execution_journal(
        execution_id: UUID,
        limit: int = 100,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {
            "items": runtime.execution_service.list_execution_journal(
                str(execution_id),
                limit=_clamp_limit(limit, cap=500),
            ),
        }

    @router.get("/orders/recent")
    def recent_orders(
        limit: int = 20,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {"items": runtime.order_service.list_recent_orders(_clamp_limit(limit))}

    @router.get("/orders/actions/recent")
    def recent_order_actions(
        limit: int = 20,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {
            "items": runtime.order_service.list_recent_order_actions(_clamp_limit(limit))
        }

    @router.get("/kill-switch/active")
    def active_kill_switches(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {"items": runtime.order_service.list_active_kill_switches()}

    @router.get("/kill-switch/events/recent")
    def recent_kill_switch_events(
        limit: int = 20,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {
            "items": runtime.order_service.list_recent_kill_switch_events(
                _clamp_limit(limit)
            )
        }

    @router.get("/audit/recent")
    def recent_audit(
        limit: int = 20,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return {"items": runtime.order_service.list_recent_audit_trails(_clamp_limit(limit))}

    @router.get("/control-plane/capability-matrix")
    def capability_matrix(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        """Family-Adapter-Matrix: explizit supported vs execution_disabled je Kategorie."""
        return runtime.control_plane.matrix_payload()

    @router.post("/control-plane/read/orders-history")
    def control_plane_read_orders_history(
        body: ControlPlaneReadHistoryRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.control_plane.read_orders_history(body))

    @router.post("/control-plane/read/fill-history")
    def control_plane_read_fill_history(
        body: ControlPlaneReadHistoryRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.control_plane.read_fill_history(body))

    @router.post("/control-plane/operator/set-leverage")
    def control_plane_operator_set_leverage(
        body: ControlPlaneSetLeverageRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.control_plane.set_leverage_operator(body))

    @router.post("/orders/create")
    def create_order(
        body: OrderCreateRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.create_order(body))

    @router.post("/orders/reduce-only")
    def create_reduce_only_order(
        body: ReduceOnlyOrderRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(
            lambda: runtime.order_service.create_reduce_only_order(body)
        )

    @router.post("/orders/cancel")
    def cancel_order(
        body: OrderCancelRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.cancel_order(body))

    @router.post("/orders/replace")
    def replace_order(
        body: OrderReplaceRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.replace_order(body))

    @router.post("/orders/query")
    def query_order(
        body: OrderQueryRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.query_order(body))

    @router.post("/kill-switch/arm")
    def arm_kill_switch(
        body: KillSwitchRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.arm_kill_switch(body))

    @router.post("/kill-switch/release")
    def release_kill_switch(
        body: KillSwitchRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.release_kill_switch(body))

    @router.post("/orders/emergency-flatten")
    def emergency_flatten(
        body: EmergencyFlattenRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.emergency_flatten(body))

    @router.post("/safety/orders/cancel-all")
    def safety_cancel_all_orders(
        body: CancelAllOrdersRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(lambda: runtime.order_service.cancel_all_orders_operator(body))

    @router.post("/safety/safety-latch/release")
    def safety_latch_release(
        body: SafetyLatchReleaseRequest,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return runtime.order_service.release_safety_latch(body)

    @router.post("/orders/timeouts/run")
    def run_order_timeouts(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict:
        return _wrap_bitget_error(runtime.order_service.run_order_timeouts)

    return router


def _wrap_bitget_error(callback):
    try:
        return callback()
    except BitgetRestError as exc:
        raise HTTPException(
            status_code=_http_status_for_classification(exc.classification),
            detail=exc.to_dict(),
        ) from exc


def _http_status_for_classification(classification: str) -> int:
    if classification in ("auth", "permission", "operator_intervention"):
        return 403
    if classification == "kill_switch":
        return 423
    if classification == "validation":
        return 400
    if classification in ("duplicate", "conflict"):
        return 409
    if classification == "not_found":
        return 404
    if classification == "rate_limit":
        return 429
    if classification == "service_disabled":
        return 412
    if classification in ("timestamp", "transport", "server", "circuit_open"):
        return 503
    return 500
