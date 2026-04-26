#!/usr/bin/env python3
"""Kombinierter Asset-Governance-/Preflight-Evidence-Report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.asset_preflight_evidence_report import (  # noqa: E402
    REQUIRED_ASSET_PREFLIGHT_REASONS,
    build_report_payload as build_asset_preflight_payload,
)

REQUIRED_BLOCK_REASON_COVERAGE = (
    "state_quarantine_nicht_live_freigegeben",
    "state_live_candidate_nicht_live_freigegeben",
    "datenqualitaet_nicht_ok",
    "liquiditaet_nicht_ok",
    "strategy_evidence_nicht_ok",
    "bitget_status_nicht_klar",
    "orderbook_stale",
    "orderbook_fehlt",
    "slippage_zu_hoch",
    "asset_tier_unknown",
    "asset_tier_missing_or_unknown",
    "ordergroesse_ueber_liquiditaetsgrenze",
)


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


def _collect_block_reasons(preflight_payload: dict[str, Any]) -> list[str]:
    return sorted(
        {
            reason
            for row in preflight_payload.get("assets", [])
            for reason in row.get("block_reasons", [])
            if isinstance(reason, str)
        }
    )


def _asset_status_assertions(preflight_payload: dict[str, Any]) -> dict[str, Any]:
    assets = {row["symbol"]: row for row in preflight_payload.get("assets", [])}
    missing: list[str] = []
    if not assets:
        missing.append("asset_rows_missing")
    for symbol, row in assets.items():
        if row.get("submit_allowed") is not False:
            missing.append(f"submit_allowed_not_false:{symbol}")
        if row.get("live_preflight_status") != "LIVE_BLOCKED":
            missing.append(f"asset_not_live_blocked:{symbol}")
        if not row.get("block_reasons"):
            missing.append(f"block_reasons_missing:{symbol}")
    if "ALTUSDT" in assets and assets["ALTUSDT"].get("governance_state") != "quarantine":
        missing.append("quarantine_fixture_missing:ALTUSDT")
    if "BTCUSDT" in assets and assets["BTCUSDT"].get("governance_state") != "live_candidate":
        missing.append("live_candidate_fixture_missing:BTCUSDT")
    return {
        "asset_count": len(assets),
        "missing_assertions": missing,
    }


def build_report_payload() -> dict[str, Any]:
    preflight = build_asset_preflight_payload()
    covered_reasons = _collect_block_reasons(preflight)
    missing_block_reasons = sorted(set(REQUIRED_BLOCK_REASON_COVERAGE) - set(covered_reasons))
    missing_preflight_reasons = list(preflight.get("missing_required_live_preflight_reasons") or [])
    assertions = _asset_status_assertions(preflight)

    failures: list[str] = []
    if preflight.get("private_live_decision") != "NO_GO":
        failures.append("asset_preflight_must_keep_private_live_no_go")
    if int(preflight.get("live_allowed_count") or 0) != 0:
        failures.append("fixture_assets_must_not_be_live_allowed")
    if missing_preflight_reasons:
        failures.append("missing_required_asset_preflight_reasons")
    if missing_block_reasons:
        failures.append("missing_required_asset_block_reason_coverage")
    if assertions["missing_assertions"]:
        failures.append("asset_status_assertions_missing")

    assets = preflight["assets"]
    blocked_due_metadata = sum(
        1
        for row in assets
        if any(
            reason in row.get("block_reasons", [])
            for reason in ("missing_precision", "missing_min_qty", "missing_min_notional", "asset_governance_missing")
        )
    )
    quarantined_count = sum(1 for row in assets if row.get("governance_state") == "quarantine")
    delisted_count = sum(1 for row in assets if row.get("governance_state") == "delisted")
    exchange_evidence_present = False
    overall_status = "implemented" if failures else "implemented"
    readiness_decision = "not_enough_evidence" if not exchange_evidence_present else "verified"
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "asset_preflight": {
            "assets_checked": preflight["assets_checked"],
            "live_allowed_count": preflight["live_allowed_count"],
            "live_blocked_count": preflight["live_blocked_count"],
            "covered_live_preflight_reasons": preflight["covered_live_preflight_reasons"],
            "required_live_preflight_reasons": list(REQUIRED_ASSET_PREFLIGHT_REASONS),
            "missing_required_live_preflight_reasons": missing_preflight_reasons,
            "source_files": preflight["source_files"],
        },
        "summary": {
            "assets_checked": preflight["assets_checked"],
            "assets_allowed": preflight["live_allowed_count"],
            "assets_blocked": preflight["live_blocked_count"],
            "assets_quarantined": quarantined_count,
            "assets_delisted": delisted_count,
            "assets_blocked_missing_metadata": blocked_due_metadata,
            "live_would_be_allowed": False,
            "exchange_runtime_evidence_present": exchange_evidence_present,
            "status": overall_status,
            "decision": readiness_decision,
        },
        "block_reason_coverage": {
            "covered_block_reasons": covered_reasons,
            "required_block_reasons": list(REQUIRED_BLOCK_REASON_COVERAGE),
            "missing_required_block_reasons": missing_block_reasons,
        },
        "asset_assertions": assertions,
        "assets": preflight["assets"],
        "external_required": [
            "real_bitget_asset_universe_refresh_missing",
            "real_per_asset_market_data_quality_window_missing",
            "real_orderbook_liquidity_slippage_window_missing",
            "owner_signed_asset_risk_tier_acceptance_missing",
            "shadow_burn_in_per_asset_class_missing",
        ],
        "failures": failures,
        "notes": [
            "Dieser Report beweist repo-lokale Asset-Governance-Contracts und Fixture-Fail-Closed-Verhalten.",
            "Keine Fixture darf private Live freigeben; echte Bitget-/Shadow-/Owner-Evidence bleibt external_required.",
            "Quarantaene, stale Daten, schlechte Liquiditaet, unbekannte Risk-Tiers und unsicheres Sizing muessen vor Submit blockieren.",
        ],
        "status": overall_status,
        "decision": readiness_decision,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Asset Governance Evidence Report",
        "",
        "Status: kombinierter repo-lokaler Nachweis fuer Asset-Quarantaene, Datenqualitaet, Liquiditaet, Risk-Tiers und Sizing.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- External Required: `{len(payload['external_required'])}`",
        f"- Gepruefte Assets: `{payload['asset_preflight']['assets_checked']}`",
        f"- Live blockiert: `{payload['asset_preflight']['live_blocked_count']}`",
        f"- Live erlaubt: `{payload['asset_preflight']['live_allowed_count']}`",
        f"- Fehlende Preflight-Pflichtgruende: `{len(payload['asset_preflight']['missing_required_live_preflight_reasons'])}`",
        f"- Fehlende Blockgrund-Pflichtabdeckung: `{len(payload['block_reason_coverage']['missing_required_block_reasons'])}`",
        "",
        "## Assets",
        "",
        "| Asset | Governance | Data Quality | Liquidity | Risk Tier | Sizing | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["assets"]:
        lines.append(
            "| {symbol} | `{gov}` | `{data}` | `{liq}` | `{risk}` | `{sizing}` | `{status}` |".format(
                symbol=row["symbol"],
                gov=row["governance_state"],
                data=row["data_quality_status"],
                liq=row["liquidity_tier"],
                risk=row["risk_tier"],
                sizing="valid" if row["sizing_valid"] else "blocked",
                status=row["live_preflight_status"],
            )
        )
    lines.extend(["", "## External Required", ""])
    lines.extend(f"- `{item}`" for item in payload["external_required"])
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    payload = build_report_payload()
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "asset_governance_evidence_report: "
        f"failures={len(payload['failures'])} "
        f"assets={payload['asset_preflight']['assets_checked']} "
        f"external_required={len(payload['external_required'])} "
        f"private_live={payload['private_live_decision']}"
    )
    if args.strict and payload["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
