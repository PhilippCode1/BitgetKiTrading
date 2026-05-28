"""Forensik-Phasen-Index (Signal bis Review)."""

from __future__ import annotations

from shared_py.observability.execution_forensic import build_forensic_timeline_phases


def test_forensic_phases_index_signal_to_review() -> None:
    events = [
        {"ts": "2026-01-01T00:00:01Z", "kind": "signal_context", "ref": "sig-1"},
        {
            "ts": "2026-01-01T00:00:02Z",
            "kind": "specialist_path_marker",
            "ref": "sig-1",
        },
        {"ts": "2026-01-01T00:00:10Z", "kind": "execution_decision", "ref": "exec-1"},
        {"ts": "2026-01-01T00:00:12Z", "kind": "operator_release", "ref": "exec-1"},
        {"ts": "2026-01-01T00:00:20Z", "kind": "order", "ref": "ord-1"},
        {"ts": "2026-01-01T00:00:21Z", "kind": "fill", "ref": "fill-1"},
        {"ts": "2026-01-01T00:00:30Z", "kind": "journal:reconcile", "ref": "j1"},
        {"ts": "2026-01-01T00:01:00Z", "kind": "exit_plan", "ref": "xp1"},
        {"ts": "2026-01-01T00:05:00Z", "kind": "trade_review", "ref": "rv1"},
        {"ts": "2026-01-01T00:06:00Z", "kind": "gateway_audit", "ref": "ga1"},
    ]
    out = build_forensic_timeline_phases(events)
    idx = out["indices_by_phase"]
    assert idx["inputs"] == [0]
    assert idx["specialists_and_decision_binding"] == [1]
    assert idx["execution_decision"] == [2]
    assert idx["operator_release"] == [3]
    assert set(idx["orders_fills_journal"]) == {4, 5, 6}
    assert idx["exit"] == [7]
    assert idx["post_trade_review"] == [8]
    assert idx["governance_audit"] == [9]
    assert out["schema_version"] == "forensic-phases-v1"
