"""
Prometheus-Metriken für strukturierte LLM-Aufrufe (latenz, Tokens, Fehlerkategorien).
Gleiche service-Logik wie instrument_fastapi: llm-orchestrator -> llm_orchestrator
"""
from __future__ import annotations

from typing import Literal

from prometheus_client import Counter, Histogram

# HTTP-Instrumentierung nutzt bis 10s; LLM SLO bis >15s (Operator Explain p95)
_LLM_DUR_BUCKETS: tuple[float, ...] = (
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
    6.0,
    7.5,
    9.0,
    10.0,
    12.0,
    15.0,
    20.0,
    30.0,
    45.0,
    60.0,
    90.0,
    120.0,
)

SERVICE = "llm_orchestrator"

# Histogram: nur echte OpenAI-HTTP-Roundtrips (kein Redis-Cache)
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "Dauer des LLM-Provider-Aufrufs bis zur Antwort (Sekunden)",
    ["service", "task_type", "provider", "transport"],
    buckets=_LLM_DUR_BUCKETS,
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Vom Provider gemeldete Token: prompt (input) vs. completion (output).",
    ["service", "task_type", "token_kind"],
)
# token_kind: prompt | completion (Prometheus-Label, Kleinschreibung)

llm_parsing_errors_total = Counter(
    "llm_parsing_errors_total",
    "JSON-Decode- oder JSON-Schema-Validierungsfehler (Antwort-Struktur).",
    ["service", "task_type", "error_kind"],
)
# error_kind: json_decode | schema_validation

llm_structured_runs_total = Counter(
    "llm_structured_runs_total",
    "Lauf run_structured (eine Anfrage) — Ergebnis success/failure.",
    ["service", "task_type", "outcome"],
)
# outcome: success | failure


def norm_task_type(task_type: str | None) -> str:
    t = (task_type or "").strip()
    return t if t else "unknown"


def add_tokens(
    task_type: str | None, *, prompt_tokens: int, completion_tokens: int
) -> None:
    tt = norm_task_type(task_type)
    p = max(0, int(prompt_tokens))
    c = max(0, int(completion_tokens))
    if p:
        llm_tokens_total.labels(SERVICE, tt, "prompt").inc(p)
    if c:
        llm_tokens_total.labels(SERVICE, tt, "completion").inc(c)


def observe_request_duration(
    task_type: str | None,
    duration_sec: float,
    provider: str,
    transport: str,
) -> None:
    d = max(0.0, float(duration_sec))
    llm_request_duration_seconds.labels(
        SERVICE, norm_task_type(task_type), provider, transport
    ).observe(d)


def record_parsing_error(
    task_type: str | None, kind: Literal["json_decode", "schema_validation"]
) -> None:
    llm_parsing_errors_total.labels(SERVICE, norm_task_type(task_type), kind).inc()


def record_structured_run_outcome(
    task_type: str | None, outcome: Literal["success", "failure"]
) -> None:
    llm_structured_runs_total.labels(
        SERVICE, norm_task_type(task_type), outcome
    ).inc()
