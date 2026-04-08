from __future__ import annotations

from shared_py.observability.correlation import log_correlation_fields, new_trace_id


def test_new_trace_id_uuid_shape() -> None:
    t = new_trace_id()
    assert len(t) == 36
    assert t.count("-") == 4


def test_log_correlation_fields_omits_empty() -> None:
    assert log_correlation_fields() == {}
    d = log_correlation_fields(
        signal_id="sig-1",
        execution_id=None,
        internal_order_id="ord",
    )
    assert d["corr_signal_id"] == "sig-1"
    assert d["corr_internal_order_id"] == "ord"
    assert "corr_execution_id" not in d
