"""
Prometheus-Metriken fuer LLM-Provider: Token, Latenz (SLO/p95), Fehler.
Exponiert via /metrics (instrument_fastapi).
"""
from __future__ import annotations

from typing import Literal

from prometheus_client import Counter, Histogram

from llm_orchestrator.llm_request_metrics_context import (
    get_metrics_model,
    get_metrics_task,
    get_metrics_tenant,
)

# Feingranulare Latenz-Buckets bis 30s, danach lange Tail fuer Timeouts
_LLM_DUR_BUCKETS: tuple[float, ...] = (
    0.02,
    0.04,
    0.06,
    0.08,
    0.1,
    0.12,
    0.15,
    0.18,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.45,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.4,
    1.5,
    1.6,
    1.7,
    1.8,
    1.9,
    2.0,
    2.2,
    2.4,
    2.5,
    2.6,
    2.8,
    3.0,
    3.2,
    3.4,
    3.5,
    3.6,
    3.8,
    4.0,
    4.2,
    4.4,
    4.5,
    4.6,
    4.8,
    5.0,
    5.2,
    5.4,
    5.5,
    5.6,
    5.8,
    6.0,
    6.2,
    6.4,
    6.5,
    6.6,
    6.8,
    7.0,
    7.2,
    7.4,
    7.5,
    7.6,
    7.8,
    8.0,
    8.2,
    8.4,
    8.5,
    8.6,
    8.8,
    9.0,
    9.2,
    9.4,
    9.5,
    9.6,
    9.8,
    10.0,
    10.2,
    10.4,
    10.5,
    10.6,
    10.8,
    11.0,
    11.2,
    11.4,
    11.5,
    11.6,
    11.8,
    12.0,
    12.2,
    12.4,
    12.5,
    12.6,
    12.8,
    13.0,
    13.2,
    13.4,
    13.5,
    13.6,
    13.8,
    14.0,
    14.2,
    14.4,
    14.5,
    14.6,
    14.8,
    15.0,
    16.0,
    17.0,
    18.0,
    19.0,
    20.0,
    22.0,
    24.0,
    25.0,
    28.0,
    30.0,
    40.0,
    50.0,
    60.0,
    90.0,
    120.0,
    180.0,
)

SERVICE = "llm_orchestrator"

# Histogram: OpenAI-HTTP-Roundtrips (kein Cache)
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "Dauer des LLM-Provider-HTTP-Aufrufs (Sekunden) bis Antwort/Usage",
    [
        "service",
        "model",
        "tenant_id",
        "task_type",
        "provider",
        "transport",
    ],
    buckets=_LLM_DUR_BUCKETS,
)

# type: prompt (input) | completion (output) — API-Wortlaut
llm_tokens_total = Counter(
    "llm_tokens_total",
    "Vom Provider gemeldete Token (usage): prompt vs. completion.",
    ["service", "model", "type", "tenant_id"],
)

llm_error_total = Counter(
    "llm_error_total",
    "Fehler bei LLM-Provider-Requests (nicht-OK / terminal failure).",
    ["service", "error_code", "provider"],
)

llm_parsing_errors_total = Counter(
    "llm_parsing_errors_total",
    "JSON-Decode- oder JSON-Schema-Validierungsfehler (Antwort-Struktur).",
    ["service", "task_type", "error_kind"],
)

llm_structured_runs_total = Counter(
    "llm_structured_runs_total",
    "Lauf run_structured (eine Anfrage) — Ergebnis success/failure.",
    ["service", "task_type", "outcome"],
)


def norm_task_type(task_type: str | None) -> str:
    t = (task_type or "").strip()
    return t if t else "unknown"


def add_tokens(*, prompt_tokens: int, completion_tokens: int) -> None:
    m = get_metrics_model()
    tid = get_metrics_tenant()
    p = max(0, int(prompt_tokens))
    c = max(0, int(completion_tokens))
    if p:
        llm_tokens_total.labels(SERVICE, m, "prompt", tid).inc(p)
    if c:
        llm_tokens_total.labels(SERVICE, m, "completion", tid).inc(c)


def observe_request_duration(
    duration_sec: float,
    provider: str,
    transport: str,
    *,
    task_type: str | None = None,
) -> None:
    """task_type-Override falls Context noch leer (Initialisierung)."""
    d = max(0.0, float(duration_sec))
    tt = norm_task_type(task_type) if task_type is not None else get_metrics_task()
    llm_request_duration_seconds.labels(
        SERVICE,
        get_metrics_model(),
        get_metrics_tenant(),
        tt,
        provider,
        transport,
    ).observe(d)


def record_llm_error(error_code: str, provider: str) -> None:
    ec = (error_code or "unknown").strip() or "unknown"
    pv = (provider or "unknown").strip() or "unknown"
    llm_error_total.labels(SERVICE, ec[:128], pv[:64]).inc()


def record_parsing_error(
    task_type: str | None, kind: Literal["json_decode", "schema_validation"]
) -> None:
    llm_parsing_errors_total.labels(
        SERVICE, norm_task_type(task_type), kind
    ).inc()


def record_structured_run_outcome(
    task_type: str | None, outcome: Literal["success", "failure"]
) -> None:
    llm_structured_runs_total.labels(
        SERVICE, norm_task_type(task_type), outcome
    ).inc()
