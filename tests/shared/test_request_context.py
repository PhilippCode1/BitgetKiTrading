from __future__ import annotations

import logging

from shared_py.observability.correlation import log_correlation_fields
from shared_py.observability.request_context import (
    RequestContextLoggingFilter,
    clear_request_context,
    set_request_context,
)


def test_log_correlation_fields_request_ids() -> None:
    d = log_correlation_fields(
        request_id="r1",
        correlation_id="c1",
    )
    assert d["corr_request_id"] == "r1"
    assert d["corr_correlation_id"] == "c1"


def test_request_context_logging_filter_sets_attrs() -> None:
    set_request_context(request_id="req-abc", correlation_id="cor-xyz")
    try:
        rec = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="m",
            args=(),
            exc_info=None,
        )
        assert RequestContextLoggingFilter().filter(rec)
        assert rec.corr_request_id == "req-abc"  # type: ignore[attr-defined]
        assert rec.corr_correlation_id == "cor-xyz"  # type: ignore[attr-defined]
    finally:
        clear_request_context()
