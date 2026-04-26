#!/usr/bin/env python3
"""Erzeugt einen kombinierten Asset-Preflight-Evidence-Report pro Symbol."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scripts.market_data_quality_report import evaluate_asset as evaluate_market_data_asset  # noqa: E402
from shared_py.asset_risk_tiers import (  # noqa: E402
    asset_tier_allows_mode,
    asset_live_eligibility_reasons,
    build_asset_risk_summary_de,
    validate_multi_asset_order_sizing,
)
from shared_py.bitget.asset_governance import (  # noqa: E402
    AssetGovernanceRecord,
    live_block_reasons,
)
from shared_py.liquidity_scoring import (  # noqa: E402
    build_liquidity_assessment,
    build_liquidity_block_reasons_de,
)
from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight  # noqa: E402

DEFAULT_GOVERNANCE = ROOT / "tests" / "fixtures" / "asset_governance_sample.json"
DEFAULT_MARKET_DATA = ROOT / "tests" / "fixtures" / "market_data_quality_sample.json"
DEFAULT_LIQUIDITY = ROOT / "tests" / "fixtures" / "liquidity_quality_sample.json"
REQUIRED_ASSET_PREFLIGHT_REASONS = (
    "asset_not_live_allowed",
    "data_quality_not_pass",
    "liquidity_not_pass",
    "slippage_too_high",
    "risk_tier_not_live_allowed",
    "order_sizing_not_safe",
    "strategy_evidence_missing_or_invalid",
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


def _load_assets(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = payload if isinstance(payload, list) else payload.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError(f"{path} muss eine Liste oder ein assets-Objekt enthalten.")
    return [item for item in assets if isinstance(item, dict)]


def _load_governance(path: Path) -> dict[str, AssetGovernanceRecord]:
    return {
        record.symbol.upper(): record
        for record in (AssetGovernanceRecord.model_validate(item) for item in _load_assets(path))
    }


def _load_market_data(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in _load_assets(path):
        evaluated = evaluate_market_data_asset(item)
        summary = evaluated["summary"]
        out[str(summary.symbol).upper()] = {
            "quality_status": summary.quality_status,
            "live_impact": summary.live_impact,
            "result": summary.result,
            "block_reasons": list(summary.block_reasons),
            "warnings": list(summary.warnings),
            "summary_de": evaluated.get("summary_de"),
        }
    return out


def _load_liquidity(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in _load_assets(path):
        assessment = build_liquidity_assessment(
            symbol=str(item.get("symbol") or "UNKNOWN"),
            bid=item.get("bid"),
            ask=item.get("ask"),
            bids=list(item.get("bids") or []),
            asks=list(item.get("asks") or []),
            orderbook_age_ms=int(item.get("orderbook_age_ms") or 0),
            max_orderbook_age_ms=int(item.get("max_orderbook_age_ms") or 0),
            planned_qty=float(item.get("planned_qty") or 0.0),
            requested_notional=float(item.get("requested_notional") or 0.0),
            status=item.get("status"),
            owner_approved_small_size=bool(item.get("owner_approved_small_size")),
        )
        out[assessment.symbol.upper()] = {
            **asdict(assessment),
            "block_reasons_de": build_liquidity_block_reasons_de(assessment.block_reasons),
            "requested_notional": float(item.get("requested_notional") or 0.0),
            "requested_leverage": int(item.get("requested_leverage") or 7),
        }
    return out


def _missing_reasons(symbol: str, sources: dict[str, object | None]) -> list[str]:
    return [f"{name}_missing" for name, value in sources.items() if value is None]


def _live_gate_status_from_data_quality(status: str | None) -> str:
    if status == "data_ok":
        return "pass"
    if status == "data_warning":
        return "warn"
    if status in {"data_stale", "data_incomplete"}:
        return "stale"
    if not status or status == "data_unknown":
        return "missing"
    return "fail"


def _live_gate_status_from_liquidity(liq: dict[str, Any] | None) -> str:
    if liq is None:
        return "missing"
    if liq.get("live_allowed") is True:
        return "pass"
    if liq.get("liquidity_tier") in {"TIER_4", "TIER_5"}:
        return "fail"
    return "warn" if liq.get("block_reasons") else "pass"


def _build_live_preflight_context_for_asset(
    *,
    gov: AssetGovernanceRecord | None,
    mdq: dict[str, Any] | None,
    liq: dict[str, Any] | None,
    risk_tier: str | None,
    sizing: dict[str, Any],
    strategy_evidence_ready: bool,
    owner_approved: bool,
) -> LivePreflightContext:
    governance_state = gov.state if gov else "missing"
    terminal_or_unknown = governance_state in {"missing", "unknown", "blocked", "delisted", "suspended", "manual_review_required", "quarantine"}
    slippage_reasons = set(liq.get("block_reasons", [])) if liq else {"slippage_unbekannt"}
    return LivePreflightContext(
        execution_mode_live=True,
        live_trade_enable=True,
        owner_approved=owner_approved,
        asset_in_catalog=gov is not None,
        asset_status_ok=not terminal_or_unknown,
        asset_live_allowed=bool(gov and gov.state == "live_allowed"),
        instrument_contract_complete=bool(gov and gov.product_type and gov.market_family),
        instrument_metadata_fresh=mdq is not None and mdq.get("quality_status") not in {"data_stale", "data_unknown"},
        data_quality_status=_live_gate_status_from_data_quality(str(mdq.get("quality_status")) if mdq else None),  # type: ignore[arg-type]
        liquidity_status=_live_gate_status_from_liquidity(liq),  # type: ignore[arg-type]
        slippage_ok=not bool(slippage_reasons & {"slippage_unbekannt", "slippage_zu_hoch"}),
        risk_tier_live_allowed=asset_tier_allows_mode(risk_tier, "live"),
        order_sizing_ok=bool(sizing.get("valid")),
        portfolio_risk_ok=True,
        strategy_evidence_ok=strategy_evidence_ready,
        bitget_readiness_ok=True,
        reconcile_ok=True,
        kill_switch_active=False,
        safety_latch_active=False,
        unknown_order_state=False,
        account_snapshot_fresh=bool(mdq and liq),
        idempotency_key=f"synthetic-asset-preflight-{gov.symbol if gov else 'missing'}",
        audit_context_present=True,
        warning_policy_allows_live={},
        checked_at="synthetic-asset-preflight-evidence",
    )


def build_report_payload(
    *,
    governance_path: Path = DEFAULT_GOVERNANCE,
    market_data_path: Path = DEFAULT_MARKET_DATA,
    liquidity_path: Path = DEFAULT_LIQUIDITY,
) -> dict[str, Any]:
    governance = _load_governance(governance_path)
    market_data = _load_market_data(market_data_path)
    liquidity = _load_liquidity(liquidity_path)
    symbols = sorted(set(governance) | set(market_data) | set(liquidity))
    rows: list[dict[str, Any]] = []

    for symbol in symbols:
        gov = governance.get(symbol)
        mdq = market_data.get(symbol)
        liq = liquidity.get(symbol)
        missing = _missing_reasons(
            symbol,
            {
                "asset_governance": gov,
                "market_data_quality": mdq,
                "liquidity_quality": liq,
            },
        )
        risk_tier = gov.risk_tier if gov else None
        data_quality_status = str(mdq.get("quality_status") if mdq else "data_unknown")
        liquidity_green = bool(liq and liq.get("live_allowed") is True)
        liquidity_status = "green" if liquidity_green else "red"
        owner_approved = bool(gov and gov.state == "live_allowed" and gov.actor == "Philipp")
        strategy_evidence_ready = bool(gov and gov.strategy_evidence_ready)
        account_context_fresh = bool(mdq and liq)
        spread_bps = liq.get("spread_bps") if liq else None
        risk_reasons = asset_live_eligibility_reasons(
            tier=risk_tier,
            data_quality_status=data_quality_status,
            liquidity_status=liquidity_status,
            strategy_evidence_ready=strategy_evidence_ready,
            owner_approved=owner_approved,
            account_context_fresh=account_context_fresh,
            spread_bps=float(spread_bps) if spread_bps is not None else None,
        )
        requested_notional = float(liq.get("requested_notional") if liq else 0.0)
        requested_leverage = int(liq.get("requested_leverage") if liq else 7)
        sizing = validate_multi_asset_order_sizing(
            symbol=symbol,
            tier=risk_tier,
            mode="live",
            requested_leverage=requested_leverage,
            requested_notional_usdt=requested_notional,
        )
        governance_reasons = live_block_reasons(gov) if gov else ["asset_governance_missing"]
        data_reasons = list(mdq.get("block_reasons", [])) if mdq else ["market_data_quality_missing"]
        liquidity_reasons = list(liq.get("block_reasons", [])) if liq else ["liquidity_quality_missing"]
        sizing_reasons = list(sizing.get("reasons", []))
        live_context = _build_live_preflight_context_for_asset(
            gov=gov,
            mdq=mdq,
            liq=liq,
            risk_tier=risk_tier,
            sizing=sizing,
            strategy_evidence_ready=strategy_evidence_ready,
            owner_approved=owner_approved,
        )
        live_decision = evaluate_live_preflight(live_context)
        all_block_reasons = list(
            dict.fromkeys(
                [
                    *missing,
                    *governance_reasons,
                    *data_reasons,
                    *liquidity_reasons,
                    *risk_reasons,
                    *sizing_reasons,
                    *live_decision.blocking_reasons,
                ]
            )
        )
        rows.append(
            {
                "symbol": symbol,
                "market_family": gov.market_family if gov else None,
                "product_type": gov.product_type if gov else None,
                "governance_state": gov.state if gov else "missing",
                "risk_tier": risk_tier,
                "data_quality_status": data_quality_status,
                "liquidity_tier": liq.get("liquidity_tier") if liq else None,
                "liquidity_live_allowed": liquidity_green,
                "requested_leverage": requested_leverage,
                "requested_notional": requested_notional,
                "sizing_valid": bool(sizing.get("valid")),
                "live_preflight_status": "LIVE_ALLOWED" if not all_block_reasons and live_decision.submit_allowed else "LIVE_BLOCKED",
                "submit_allowed": live_decision.submit_allowed,
                "live_preflight_blocking_reasons": live_decision.blocking_reasons,
                "live_preflight_missing_gates": live_decision.missing_gates,
                "block_reasons": all_block_reasons,
                "liquidity_reasons_de": liq.get("block_reasons_de") if liq else [],
                "risk_summary_de": build_asset_risk_summary_de(
                    symbol=symbol,
                    tier=risk_tier,
                    reasons=risk_reasons or ["keine_risk_tier_blocker"],
                    max_leverage=int(sizing.get("effective_leverage", 1)),
                    max_notional_usdt=float(sizing.get("effective_notional_usdt", 0.0)),
                ),
            }
        )

    live_allowed = [row["symbol"] for row in rows if row["live_preflight_status"] == "LIVE_ALLOWED"]
    covered_preflight_reasons = sorted(
        {
            reason
            for row in rows
            for reason in row.get("live_preflight_blocking_reasons", [])
            if isinstance(reason, str)
        }
    )
    missing_required_preflight_reasons = [
        reason for reason in REQUIRED_ASSET_PREFLIGHT_REASONS if reason not in covered_preflight_reasons
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "source_files": {
            "asset_governance": str(governance_path.relative_to(ROOT)),
            "market_data_quality": str(market_data_path.relative_to(ROOT)),
            "liquidity_quality": str(liquidity_path.relative_to(ROOT)),
        },
        "assets_checked": len(rows),
        "live_allowed_count": len(live_allowed),
        "live_blocked_count": len(rows) - len(live_allowed),
        "live_allowed_assets": live_allowed,
        "covered_live_preflight_reasons": covered_preflight_reasons,
        "missing_required_live_preflight_reasons": missing_required_preflight_reasons,
        "assets": rows,
        "private_live_decision": "NO_GO" if live_allowed else "NO_GO",
        "notes": [
            "Repo-lokale Fixture-Evidence; keine echte Bitget-/Shadow-/Owner-Evidence.",
            "LIVE_ALLOWED in diesem Report waere nur technisch vorpruefbar, nicht private_live_allowed.",
            "Fehlende Governance-, Datenqualitaets-, Liquiditaets- oder Risk-Tier-Evidence blockiert fail-closed.",
            "Live-Broker-Preflight-Codes werden als Schnittstelle mitbelegt; fehlende Required-Codes bleiben P0-Evidence-Gap.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Asset Preflight Evidence Report",
        "",
        "Status: kombinierte repo-lokale Fixture-Evidence fuer Asset Governance, Datenqualitaet, Liquiditaet und Risk-Tiers.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Gepruefte Assets: `{payload['assets_checked']}`",
        f"- Live technisch blockiert: `{payload['live_blocked_count']}`",
        f"- Live technisch erlaubt: `{payload['live_allowed_count']}`",
        f"- Private-Live-Entscheidung: `{payload['private_live_decision']}`",
        f"- Abgedeckte Live-Preflight-Blockgruende: `{len(payload['covered_live_preflight_reasons'])}`",
        f"- Fehlende Required-Preflight-Blockgruende: `{len(payload['missing_required_live_preflight_reasons'])}`",
        "",
        "## Assets",
        "",
        "| Asset | Governance | Data Quality | Liquidity | Risk Tier | Sizing | Status | Blockgruende |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["assets"]:
        reasons = ", ".join(f"`{item}`" for item in row["block_reasons"]) or "-"
        lines.append(
            "| {symbol} | `{gov}` | `{data}` | `{liq}` | `{risk}` | `{sizing}` | `{status}` | {reasons} |".format(
                symbol=row["symbol"],
                gov=row["governance_state"],
                data=row["data_quality_status"],
                liq=row["liquidity_tier"],
                risk=row["risk_tier"],
                sizing="valid" if row["sizing_valid"] else "blocked",
                status=row["live_preflight_status"],
                reasons=reasons,
            )
        )
    lines.extend(["", "## Live-Broker-Preflight-Coverage", ""])
    covered = ", ".join(f"`{item}`" for item in payload["covered_live_preflight_reasons"]) or "-"
    missing = ", ".join(f"`{item}`" for item in payload["missing_required_live_preflight_reasons"]) or "-"
    lines.append(f"- Abgedeckt: {covered}")
    lines.append(f"- Fehlend: {missing}")
    lines.extend(["", "## Deutsche Risk-Hinweise", ""])
    for row in payload["assets"]:
        lines.append(f"- `{row['symbol']}`: {row['risk_summary_de']}")
        for reason in row["liquidity_reasons_de"]:
            lines.append(f"  - Liquiditaet: {reason}")
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--governance-json", type=Path, default=DEFAULT_GOVERNANCE)
    parser.add_argument("--market-data-json", type=Path, default=DEFAULT_MARKET_DATA)
    parser.add_argument("--liquidity-json", type=Path, default=DEFAULT_LIQUIDITY)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    payload = build_report_payload(
        governance_path=args.governance_json,
        market_data_path=args.market_data_json,
        liquidity_path=args.liquidity_json,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "asset_preflight_evidence_report: "
        f"assets={payload['assets_checked']} "
        f"blocked={payload['live_blocked_count']} "
        f"live_allowed={payload['live_allowed_count']} "
        f"missing_required_preflight_reasons={len(payload['missing_required_live_preflight_reasons'])}"
    )
    if args.strict and payload["missing_required_live_preflight_reasons"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
