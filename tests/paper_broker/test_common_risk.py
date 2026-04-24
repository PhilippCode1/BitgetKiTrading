from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
PAPER_SRC = ROOT / "services" / "paper-broker" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (ROOT, PAPER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from paper_broker.risk.common_risk import build_paper_account_risk_metrics
from paper_broker.storage import repo_position_events, repo_positions


def test_build_paper_account_risk_metrics_uses_total_equity_and_window_history(
    monkeypatch,
) -> None:
    account_id = UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        repo_positions,
        "list_open_positions",
        lambda _conn, tenant_id="default": [
            {
                "account_id": str(account_id),
                "state": "open",
                "isolated_margin": "500",
            },
            {
                "account_id": "00000000-0000-0000-0000-000000000002",
                "state": "open",
                "isolated_margin": "999",
            },
        ],
    )

    def _equity_points(
        _conn, *, account_id, tenant_id="default", since_ts_ms=None, limit=5000
    ):
        assert str(account_id) == "00000000-0000-0000-0000-000000000001"
        if since_ts_ms is None:
            return ["10200"]
        if since_ts_ms >= 9_913_600_000:
            return ["10050"]
        return ["10100"]

    monkeypatch.setattr(
        repo_position_events, "list_account_equity_points", _equity_points
    )

    metrics = build_paper_account_risk_metrics(
        None,  # type: ignore[arg-type]
        account_id=account_id,
        tenant_id="default",
        account_row={"equity": "9400", "initial_equity": "10000"},
        now_ms=10_000_000_000,
        projected_margin="100",
        projected_fee="25",
    )

    assert str(metrics["total_equity"]) == "9900"
    assert str(metrics["projected_total_equity"]) == "9875"
    assert metrics["current_margin_usage_pct"] == 0.050505
    assert metrics["projected_margin_usage_pct"] == 0.060759
    assert metrics["account_drawdown_pct"] == 0.031863
    assert metrics["daily_drawdown_pct"] == 0.017413
    assert metrics["weekly_drawdown_pct"] == 0.022277
    assert str(metrics["daily_loss_usdt"]) == "175"
