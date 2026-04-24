from shared_py.observability.apex_trace import (
    finalize_apex_deltas,
    new_apex_trace,
    set_hop,
)


def test_finalize_three_hops_deltas() -> None:
    a = new_apex_trace()
    a = set_hop(a, "signal_engine", 1_000_000_000, 1_000_500_000)
    a = set_hop(a, "message_queue", 1_000_600_000, 1_000_600_000)
    a = set_hop(a, "live_broker", 1_000_800_000, 1_001_000_000)
    out = finalize_apex_deltas(a)
    d = out.get("deltas_ms") or {}
    assert "signal_engine->message_queue" in d
    assert "message_queue->live_broker" in d
    assert d.get("signal_engine_self_ms") is not None
