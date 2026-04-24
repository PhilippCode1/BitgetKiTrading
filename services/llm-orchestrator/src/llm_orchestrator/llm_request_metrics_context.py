"""
Request-scharfe Werte fuer LLM-Prometheus-Metriken (model, tenant, task) —
gesetzt in run_structured und vor jedem Provider-Aufruf aktualisiert (model pro Chain).
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any

_tenant: ContextVar[str] = ContextVar("llm_metrics_tenant", default="unknown")
_model: ContextVar[str] = ContextVar("llm_metrics_model", default="unknown")
_task: ContextVar[str] = ContextVar("llm_metrics_task", default="unknown")

_VALID_LABEL = re.compile(r"^[a-zA-Z0-9_:\-./+]{1,256}$")


def _norm(s: str | None, default: str = "unknown", *, max_len: int = 128) -> str:
    t = (s or "").strip() or default
    t = t[:max_len]
    if _VALID_LABEL.match(t):
        return t
    alnum = re.sub(r"[^a-zA-Z0-9_\-]", "_", t)[:max_len] or default
    return alnum


def set_llm_request_metrics(
    *, tenant_id: str | None, task_type: str | None, model: str | None
) -> None:
    _tenant.set(_norm(tenant_id, "unknown", max_len=64))
    _task.set(_norm(task_type, "unknown", max_len=64))
    _model.set(_norm(model, "unknown", max_len=128))


def get_metrics_tenant() -> str:
    return _tenant.get()


def get_metrics_model() -> str:
    return _model.get()


def get_metrics_task() -> str:
    return _task.get()


def extract_tenant_id_from_object(obj: Any) -> str:
    if not isinstance(obj, dict):
        return "unknown"
    for key in (
        "tenant_id",
        "tenant_partition_id",
        "partition_id",
        "tenantId",
        "org_id",
    ):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return _norm(v.strip(), "unknown", max_len=64)
    inner = obj.get("tenant")
    if isinstance(inner, str) and inner.strip():
        return _norm(inner.strip(), "unknown", max_len=64)
    ctx = obj.get("context")
    if isinstance(ctx, dict):
        tid = extract_tenant_id_from_object(ctx)
        if tid != "unknown":
            return tid
    return "unknown"
