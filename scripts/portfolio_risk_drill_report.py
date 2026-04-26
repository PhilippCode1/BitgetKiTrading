#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.portfolio_risk_controls import ExposureItem, PortfolioRiskLimits, PortfolioSnapshot, evaluate_portfolio_risk


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _limits() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_total_notional=20_000.0,
        max_margin_usage=0.4,
        max_largest_position_risk=0.03,
        max_concurrent_positions=3,
        max_pending_orders=2,
        max_pending_live_candidates=1,
        max_net_directional_exposure=15_000.0,
        max_correlation_stress=0.75,
        max_funding_concentration=0.03,
        max_family_exposure=16_000.0,
        max_total_leverage_exposure=3.0,
        max_asset_exposure=12_000.0,
        max_correlation_group_exposure=13_000.0,
        max_daily_loss=400.0,
        max_weekly_loss=1_000.0,
        max_intraday_drawdown=0.08,
        max_total_drawdown=0.18,
        max_consecutive_losses=4,
    )


def _base_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        open_positions=[ExposureItem("BTCUSDT", "futures", 8_000.0, 0.01, "long")],
        pending_orders=[],
        pending_live_candidates=[],
        account_equity=10_000.0,
        free_margin=7_000.0,
        used_margin=3_000.0,
        snapshot_fresh=True,
        correlation_stress=0.2,
        unknown_correlation=False,
        total_leverage_exposure=2.0,
        exposure_by_asset={"BTCUSDT": 8_000.0},
        exposure_by_market_family={"futures": 8_000.0},
        exposure_by_correlation_group={"majors": 8_000.0},
        owner_limits_present=True,
        daily_realized_pnl=100.0,
        daily_unrealized_pnl=50.0,
        weekly_pnl=300.0,
        current_drawdown=0.03,
        max_drawdown=0.07,
    )


def _scenario_rows() -> list[dict[str, Any]]:
    b = _base_snapshot()
    scenarios: list[tuple[str, PortfolioSnapshot, bool]] = [
        ("normalzustand", b, True),
        ("max_asset_exposure_verletzt", PortfolioSnapshot(**{**b.__dict__, "exposure_by_asset": {"BTCUSDT": 14_000.0}}), False),
        ("max_family_exposure_verletzt", PortfolioSnapshot(**{**b.__dict__, "exposure_by_market_family": {"futures": 18_000.0}}), False),
        ("max_correlation_exposure_verletzt", PortfolioSnapshot(**{**b.__dict__, "exposure_by_correlation_group": {"majors": 14_000.0}}), False),
        ("daily_loss_limit_erreicht", PortfolioSnapshot(**{**b.__dict__, "daily_realized_pnl": -500.0}), False),
        ("weekly_loss_limit_erreicht", PortfolioSnapshot(**{**b.__dict__, "weekly_pnl": -1500.0}), False),
        ("drawdown_limit_erreicht", PortfolioSnapshot(**{**b.__dict__, "current_drawdown": 0.11}), False),
        ("loss_streak_limit_erreicht", PortfolioSnapshot(**{**b.__dict__, "current_loss_streak": 6}), False),
        ("global_halt_aktiv", PortfolioSnapshot(**{**b.__dict__, "global_halt_active": True}), False),
        ("risk_state_unknown", PortfolioSnapshot(**{**b.__dict__, "snapshot_fresh": False}), False),
        ("reduce_only_nach_loss_limit", PortfolioSnapshot(**{**b.__dict__, "daily_realized_pnl": -500.0}), False),
        ("opening_order_nach_halt_blockiert", PortfolioSnapshot(**{**b.__dict__, "global_halt_active": True}), False),
    ]
    out: list[dict[str, Any]] = []
    limits = _limits()
    for scenario, snapshot, expected in scenarios:
        result = evaluate_portfolio_risk(snapshot, limits)
        actual = bool(result.opening_orders_allowed)
        out.append(
            {
                "scenario": scenario,
                "expected_decision": "ALLOW_OPENING" if expected else "BLOCK_OPENING",
                "actual_decision": "ALLOW_OPENING" if actual else "BLOCK_OPENING",
                "pass": expected == actual,
                "reasons": result.block_reasons,
                "risk_state": result.risk_state,
                "reduce_only_allowed": result.reduce_only_allowed,
                "evidence_level": "synthetic",
                "live_allowed": actual,
            }
        )
    return out


def build_payload() -> dict[str, Any]:
    scenarios = _scenario_rows()
    all_pass = all(row["pass"] for row in scenarios)
    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "status": "implemented",
        "decision": "NOT_ENOUGH_EVIDENCE",
        "verified": False,
        "evidence_level": "synthetic",
        "live_allowed": False,
        "all_scenarios_passed": all_pass,
        "scenarios": scenarios,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Portfolio Risk Drill Report",
        "",
        f"- Generiert: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Verified: `{payload['verified']}`",
        f"- Evidence-Level: `{payload['evidence_level']}`",
        "",
    ]
    for row in payload["scenarios"]:
        lines.append(
            f"- `{row['scenario']}`: expected={row['expected_decision']} actual={row['actual_decision']} pass={row['pass']} reasons={','.join(row['reasons']) or '-'}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Portfolio Risk Drill Report")
    parser.add_argument("--output-md", default="reports/portfolio_risk_drill.md")
    parser.add_argument("--output-json", default="reports/portfolio_risk_drill.json")
    args = parser.parse_args()
    payload = build_payload()
    out_md = Path(args.output_md)
    out_json = Path(args.output_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(payload), encoding="utf-8")
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"portfolio_risk_drill_report: scenarios={len(payload['scenarios'])} verified={payload['verified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
