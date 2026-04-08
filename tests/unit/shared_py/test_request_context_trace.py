"""Kontextvars fuer Request-/Correlation-ID."""

from __future__ import annotations

from shared_py.observability.request_context import (
    clear_request_context,
    get_current_trace_ids,
    set_request_context,
)


def test_get_current_trace_ids_roundtrip() -> None:
    try:
        set_request_context(request_id="req-a", correlation_id="corr-b")
        assert get_current_trace_ids() == ("req-a", "corr-b")
    finally:
        clear_request_context()


def test_get_current_trace_ids_empty_after_clear() -> None:
    set_request_context(request_id="r1", correlation_id="c1")
    clear_request_context()
    assert get_current_trace_ids() == (None, None)
