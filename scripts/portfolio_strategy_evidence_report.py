#!/usr/bin/env python3
"""Erzeugt kombinierte Evidence fuer Portfolio-Risk und Strategy-Validation."""

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

from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight  # noqa: E402
from shared_py.multi_asset_strategy_evidence import (  # noqa: E402
    MultiAssetStrategyEvidence,
    evaluate_multi_asset_strategy_evidence,
)
from shared_py.portfolio_risk_controls import (  # noqa: E402
    ExposureItem,
    PortfolioRiskLimits,
    PortfolioSnapshot,
    build_portfolio_risk_summary_de,
    evaluate_portfolio_risk,
)
from shared_py.strategy_asset_evidence import (  # noqa: E402
    StrategyAssetEvidence,
    build_strategy_asset_evidence_summary_de,
    validate_strategy_asset_evidence,
)

DEFAULT_STRATEGY_ASSET_INPUT = ROOT / "tests" / "fixtures" / "strategy_asset_evidence_sample.json"
DEFAULT_MULTI_ASSET_INPUT = ROOT / "tests" / "fixtures" / "multi_asset_strategy_evidence_sample.json"
DEFAULT_EXTERNAL_TEMPLATE = ROOT / "docs" / "production_10_10" / "portfolio_strategy_evidence.template.json"

EXTERNAL_SCHEMA_VERSION = 1

REQUIRED_PORTFOLIO_BLOCK_REASONS = (
    "portfolio_snapshot_fehlt",
    "portfolio_snapshot_stale",
    "account_equity_ungueltig",
    "total_exposure_ueber_limit",
    "margin_usage_ueber_limit",
    "largest_position_risk_ueber_limit",
    "max_concurrent_positions_ueberschritten",
    "zu_viele_pending_orders",
    "zu_viele_pending_live_candidates",
    "net_long_exposure_ueber_limit",
    "net_short_exposure_ueber_limit",
    "correlation_stress_zu_hoch",
    "funding_konzentration_zu_hoch",
    "family_exposure_zu_hoch",
)

REQUIRED_STRATEGY_BLOCK_REASONS = (
    "asset_class_unknown",
    "evidence_status_nicht_live_faehig",
    "strategy_evidence_expired",
    "risk_tier_mismatch",
    "data_quality_mismatch",
    "strategy_scope_mismatch",
    "fees_fehlen",
    "spread_fehlt",
    "slippage_fehlt",
    "drawdown_fehlt",
    "zu_wenige_trades",
    "out_of_sample_fehlt_oder_nicht_bestanden",
    "walk_forward_fehlt_oder_nicht_bestanden",
    "paper_evidence_fehlt_oder_nicht_bestanden",
    "shadow_evidence_fehlt_oder_nicht_bestanden",
    "risk_per_trade_unbekannt",
    "parameter_hash_fehlt",
    "parameter_nicht_reproduzierbar",
)

REQUIRED_MULTI_ASSET_STRATEGY_REASONS = (
    "Walk-forward-Evidence fehlt.",
    "Shadow-Burn-in-Evidence fehlt.",
    "Slippage/Fees/Funding-Evidence fehlt.",
    "Datenqualität nicht ausreichend.",
    "Negative oder null Expectancy nach Kosten.",
)

SECRET_LIKE_KEYS = ("secret", "api_key", "passphrase", "token", "password", "authorization")


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def build_external_evidence_template() -> dict[str, Any]:
    return {
        "schema_version": EXTERNAL_SCHEMA_VERSION,
        "status": "external_required",
        "evidence_environment": "CHANGE_ME_STAGING_OR_SHADOW",
        "git_sha": "CHANGE_ME_GIT_SHA",
        "generated_at": "CHANGE_ME_ISO8601",
        "owner_limits": {
            "signed_by": "CHANGE_ME_OWNER_PHILIPP",
            "signed_at": "CHANGE_ME_ISO8601",
            "max_total_notional": None,
            "max_margin_usage": None,
            "max_family_exposure": None,
            "max_net_directional_exposure": None,
            "max_correlation_stress": None,
            "document_uri": "CHANGE_ME_OWNER_SIGNED_LIMITS_URI",
        },
        "portfolio_drill": {
            "runtime_snapshot_fresh": False,
            "missing_snapshot_blocks_live": False,
            "stale_snapshot_blocks_live": False,
            "exposure_limit_blocks_live": False,
            "correlation_unknown_blocks_live": False,
            "family_exposure_blocks_live": False,
            "pending_orders_counted_in_exposure": False,
            "live_orders_submitted_during_drill": False,
            "report_uri": "CHANGE_ME_PORTFOLIO_DRILL_REPORT_URI",
        },
        "strategy_validation": {
            "asset_classes_covered": [],
            "backtest_reports_present": False,
            "walk_forward_reports_present": False,
            "paper_reports_present": False,
            "shadow_reports_present": False,
            "slippage_fees_funding_included": False,
            "drawdown_limits_passed": False,
            "no_trade_quality_checked": False,
            "lineage_documented": False,
            "report_uri": "CHANGE_ME_STRATEGY_VALIDATION_REPORT_URI",
        },
        "shadow_burn_in": {
            "real_shadow_period_started_at": "CHANGE_ME_ISO8601",
            "real_shadow_period_ended_at": "CHANGE_ME_ISO8601",
            "shadow_passed": False,
            "divergence_report_uri": "CHANGE_ME_SHADOW_DIVERGENCE_REPORT_URI",
        },
        "safety": {
            "secrets_redacted": True,
            "real_orders_possible": False,
            "operator_approval_record_uri": "CHANGE_ME_OPERATOR_APPROVAL_URI",
        },
    }


def _contains_secret_surface(value: Any, path: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if any(marker in str(key).lower() for marker in SECRET_LIKE_KEYS):
                if isinstance(child, str) and child not in {None, "", "REDACTED", "CHANGE_ME_REDACTED"}:
                    issues.append(f"{child_path} muss redacted sein")
            issues.extend(_contains_secret_surface(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            issues.extend(_contains_secret_surface(child, f"{path}[{idx}]"))
    elif isinstance(value, str) and any(marker in value.lower() for marker in ("bitget_", "sk-", "eyj")):
        issues.append(f"{path} enthaelt secret-aehnlichen Wert")
    return issues


def _missing_or_template(value: Any) -> bool:
    return value is None or value == "" or value == [] or str(value).startswith("CHANGE_ME")


def assess_external_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != EXTERNAL_SCHEMA_VERSION:
        failures.append("schema_version_unbekannt")
    if payload.get("status") != "verified":
        failures.append("external_status_nicht_verified")
    if str(payload.get("evidence_environment", "")).startswith("CHANGE_ME"):
        failures.append("evidence_environment_template")
    if str(payload.get("git_sha", "")).startswith("CHANGE_ME"):
        failures.append("git_sha_template")

    owner_limits = payload.get("owner_limits") or {}
    for key in (
        "signed_by",
        "signed_at",
        "max_total_notional",
        "max_margin_usage",
        "max_family_exposure",
        "max_net_directional_exposure",
        "max_correlation_stress",
        "document_uri",
    ):
        value = owner_limits.get(key)
        if _missing_or_template(value):
            failures.append(f"owner_limits_{key}_fehlt")

    portfolio_drill = payload.get("portfolio_drill") or {}
    for key in (
        "runtime_snapshot_fresh",
        "missing_snapshot_blocks_live",
        "stale_snapshot_blocks_live",
        "exposure_limit_blocks_live",
        "correlation_unknown_blocks_live",
        "family_exposure_blocks_live",
        "pending_orders_counted_in_exposure",
    ):
        if portfolio_drill.get(key) is not True:
            failures.append(f"portfolio_drill_{key}_nicht_belegt")
    if portfolio_drill.get("live_orders_submitted_during_drill") is not False:
        failures.append("portfolio_drill_darf_keine_live_orders_senden")

    strategy_validation = payload.get("strategy_validation") or {}
    if not strategy_validation.get("asset_classes_covered"):
        failures.append("strategy_asset_classes_covered_fehlt")
    for key in (
        "backtest_reports_present",
        "walk_forward_reports_present",
        "paper_reports_present",
        "shadow_reports_present",
        "slippage_fees_funding_included",
        "drawdown_limits_passed",
        "no_trade_quality_checked",
        "lineage_documented",
    ):
        if strategy_validation.get(key) is not True:
            failures.append(f"strategy_validation_{key}_nicht_belegt")

    shadow_burn_in = payload.get("shadow_burn_in") or {}
    if shadow_burn_in.get("shadow_passed") is not True:
        failures.append("shadow_burn_in_nicht_passed")
    for key in ("real_shadow_period_started_at", "real_shadow_period_ended_at", "divergence_report_uri"):
        value = shadow_burn_in.get(key)
        if _missing_or_template(value):
            failures.append(f"shadow_burn_in_{key}_fehlt")

    safety = payload.get("safety") or {}
    if safety.get("secrets_redacted") is not True:
        failures.append("secrets_redacted_nicht_belegt")
    if safety.get("real_orders_possible") is not False:
        failures.append("real_orders_possible_muss_false_sein")
    if str(safety.get("operator_approval_record_uri", "")).startswith("CHANGE_ME"):
        failures.append("operator_approval_record_uri_template")

    secret_issues = _contains_secret_surface(payload)
    failures.extend(secret_issues)

    return {
        "status": "PASS" if not failures else "FAIL",
        "external_required": bool(failures),
        "failures": list(dict.fromkeys(failures)),
    }


def _limits() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_total_notional=20_000.0,
        max_margin_usage=0.40,
        max_largest_position_risk=0.03,
        max_concurrent_positions=3,
        max_pending_orders=2,
        max_pending_live_candidates=1,
        max_net_directional_exposure=12_000.0,
        max_correlation_stress=0.75,
        max_funding_concentration=0.02,
        max_family_exposure=15_000.0,
    )


def _item(
    symbol: str,
    notional: float,
    *,
    side: str = "long",
    family: str = "futures",
    risk_pct: float = 0.01,
    funding_rate_abs: float = 0.001,
) -> ExposureItem:
    return ExposureItem(
        symbol=symbol,
        market_family=family,
        notional=notional,
        risk_pct=risk_pct,
        side=side,  # type: ignore[arg-type]
        funding_rate_abs=funding_rate_abs,
        basis_bps_abs=5.0,
    )


def _snapshot(**overrides: Any) -> PortfolioSnapshot:
    payload = {
        "open_positions": [_item("BTCUSDT", 4_000.0)],
        "pending_orders": [],
        "pending_live_candidates": [],
        "account_equity": 10_000.0,
        "used_margin": 2_000.0,
        "snapshot_fresh": True,
        "correlation_stress": 0.30,
        "unknown_correlation": False,
    }
    payload.update(overrides)
    return PortfolioSnapshot(**payload)


def _portfolio_scenarios() -> dict[str, PortfolioSnapshot | None]:
    return {
        "missing_snapshot": None,
        "stale_snapshot": _snapshot(snapshot_fresh=False),
        "invalid_equity": _snapshot(account_equity=0.0),
        "total_exposure_over_limit": _snapshot(open_positions=[_item("BTCUSDT", 30_000.0)]),
        "margin_usage_over_limit": _snapshot(used_margin=7_000.0),
        "largest_position_risk_over_limit": _snapshot(open_positions=[_item("BTCUSDT", 3_000.0, risk_pct=0.08)]),
        "max_concurrent_positions": _snapshot(
            open_positions=[
                _item("BTCUSDT", 1_000.0),
                _item("ETHUSDT", 1_000.0),
                _item("SOLUSDT", 1_000.0),
                _item("XRPUSDT", 1_000.0),
            ]
        ),
        "pending_orders_over_limit": _snapshot(
            pending_orders=[_item("AUSDT", 500.0), _item("BUSDT", 500.0), _item("CUSDT", 500.0)]
        ),
        "pending_live_candidates_over_limit": _snapshot(
            pending_live_candidates=[_item("SOLUSDT", 500.0), _item("ADAUSDT", 500.0)]
        ),
        "net_long_exposure_over_limit": _snapshot(open_positions=[_item("BTCUSDT", 13_000.0)]),
        "net_short_exposure_over_limit": _snapshot(open_positions=[_item("BTCUSDT", 13_000.0, side="short")]),
        "correlation_stress_over_limit": _snapshot(correlation_stress=0.90),
        "funding_concentration_over_limit": _snapshot(open_positions=[_item("BTCUSDT", 1_000.0, funding_rate_abs=0.04)]),
        "family_exposure_over_limit": _snapshot(open_positions=[_item("BTCUSDT", 16_000.0, family="futures")]),
    }


def _preflight_decision(*, portfolio_ok: bool = True, strategy_ok: bool = True) -> dict[str, Any]:
    decision = evaluate_live_preflight(
        LivePreflightContext(
            execution_mode_live=True,
            live_trade_enable=True,
            owner_approved=True,
            asset_in_catalog=True,
            asset_status_ok=True,
            asset_live_allowed=True,
            instrument_contract_complete=True,
            instrument_metadata_fresh=True,
            data_quality_status="pass",
            liquidity_status="pass",
            slippage_ok=True,
            risk_tier_live_allowed=True,
            order_sizing_ok=True,
            portfolio_risk_ok=portfolio_ok,
            strategy_evidence_ok=strategy_ok,
            bitget_readiness_ok=True,
            reconcile_ok=True,
            kill_switch_active=False,
            safety_latch_active=False,
            unknown_order_state=False,
            account_snapshot_fresh=True,
            idempotency_key="idem-ok",
            audit_context_present=True,
            checked_at="synthetic-portfolio-strategy-evidence",
        )
    )
    return {
        "submit_allowed": decision.submit_allowed,
        "blocking_reasons": decision.blocking_reasons,
        "missing_gates": decision.missing_gates,
    }


def _load_strategy_asset_items(path: Path) -> list[StrategyAssetEvidence]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [StrategyAssetEvidence(**row) for row in payload.get("items", [])]


def _synthetic_strategy_asset_items() -> list[StrategyAssetEvidence]:
    return [
        StrategyAssetEvidence(
            strategy_id="synthetic_research_only_guard",
            strategy_version="0.1.0",
            playbook_id="playbook_synthetic_research_only",
            asset_symbol="ETHUSDT",
            asset_class="mid_liquidity",
            market_family="futures",
            risk_tier="RISK_TIER_2_LIQUID",
            data_quality_status="data_ok",
            evidence_status="research_only",
            backtest_available=False,
            walk_forward_available=False,
            paper_available=False,
            shadow_available=False,
            shadow_passed=False,
            expires_at="2027-01-01T00:00:00Z",
            scope_asset_symbols=["ETHUSDT"],
            scope_asset_classes=["mid_liquidity"],
            allowed_market_families=["futures"],
            allowed_risk_tiers=["RISK_TIER_2_LIQUID"],
        )
    ]


def _load_multi_asset_items(path: Path) -> list[MultiAssetStrategyEvidence]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("items", payload)
    return [MultiAssetStrategyEvidence(**row) for row in rows]


def build_report_payload(
    *,
    strategy_asset_input: Path = DEFAULT_STRATEGY_ASSET_INPUT,
    multi_asset_input: Path = DEFAULT_MULTI_ASSET_INPUT,
    external_evidence_json: Path = DEFAULT_EXTERNAL_TEMPLATE,
) -> dict[str, Any]:
    portfolio_rows: list[dict[str, Any]] = []
    for scenario_id, snapshot in _portfolio_scenarios().items():
        result = evaluate_portfolio_risk(snapshot, _limits())
        portfolio_rows.append(
            {
                "id": scenario_id,
                "blocks_live": bool(result.block_reasons),
                "block_reasons": result.block_reasons,
                "cap_reasons": result.cap_reasons,
                "portfolio_result": asdict(result),
                "summary_de": build_portfolio_risk_summary_de(result),
                "preflight": _preflight_decision(portfolio_ok=not bool(result.block_reasons)),
            }
        )

    strategy_asset_rows: list[dict[str, Any]] = []
    for item in [*_load_strategy_asset_items(strategy_asset_input), *_synthetic_strategy_asset_items()]:
        reasons = validate_strategy_asset_evidence(item)
        strategy_asset_rows.append(
            {
                "strategy_id": item.strategy_id,
                "strategy_version": item.strategy_version,
                "asset_symbol": item.asset_symbol,
                "asset_class": item.asset_class,
                "market_family": item.market_family,
                "evidence_status": item.evidence_status,
                "blocks_live": bool(reasons),
                "block_reasons": reasons,
                "summary_de": build_strategy_asset_evidence_summary_de(item),
                "preflight": _preflight_decision(strategy_ok=not bool(reasons)),
            }
        )

    multi_asset_rows: list[dict[str, Any]] = []
    for item in _load_multi_asset_items(multi_asset_input):
        verdict, reasons, text = evaluate_multi_asset_strategy_evidence(item)
        multi_asset_rows.append(
            {
                "strategy_id": item.strategy_id,
                "strategy_version": item.strategy_version,
                "asset_symbol": item.asset_symbol,
                "asset_class": item.asset_class,
                "market_family": item.market_family,
                "verdict": verdict,
                "blocks_live": verdict == "FAIL",
                "block_reasons_de": reasons,
                "summary_de": text,
                "preflight": _preflight_decision(strategy_ok=verdict != "FAIL"),
            }
        )

    external_payload = json.loads(external_evidence_json.read_text(encoding="utf-8"))
    external_assessment = assess_external_evidence(external_payload)

    covered_portfolio_reasons = sorted(
        {
            reason
            for row in portfolio_rows
            for reason in [*row["block_reasons"], *row["cap_reasons"]]
        }
    )
    covered_strategy_reasons = sorted(
        {reason for row in strategy_asset_rows for reason in row["block_reasons"]}
    )
    covered_multi_asset_reasons = sorted(
        {reason for row in multi_asset_rows for reason in row["block_reasons_de"]}
    )
    covered_live_preflight_reasons = sorted(
        {
            reason
            for row in [*portfolio_rows, *strategy_asset_rows, *multi_asset_rows]
            for reason in row["preflight"]["blocking_reasons"]
        }
    )

    missing_portfolio = [reason for reason in REQUIRED_PORTFOLIO_BLOCK_REASONS if reason not in covered_portfolio_reasons]
    missing_strategy = [reason for reason in REQUIRED_STRATEGY_BLOCK_REASONS if reason not in covered_strategy_reasons]
    missing_multi_asset = [
        reason for reason in REQUIRED_MULTI_ASSET_STRATEGY_REASONS if reason not in covered_multi_asset_reasons
    ]
    missing_preflight = [
        reason
        for reason in ("portfolio_risk_not_safe", "strategy_evidence_missing_or_invalid")
        if reason not in covered_live_preflight_reasons
    ]

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "portfolio_scenarios": portfolio_rows,
        "strategy_asset_scenarios": strategy_asset_rows,
        "multi_asset_strategy_scenarios": multi_asset_rows,
        "external_evidence_assessment": external_assessment,
        "covered_portfolio_block_reasons": covered_portfolio_reasons,
        "missing_portfolio_block_reasons": missing_portfolio,
        "covered_strategy_block_reasons": covered_strategy_reasons,
        "missing_strategy_block_reasons": missing_strategy,
        "covered_multi_asset_strategy_reasons": covered_multi_asset_reasons,
        "missing_multi_asset_strategy_reasons": missing_multi_asset,
        "covered_live_preflight_reasons": covered_live_preflight_reasons,
        "missing_live_preflight_reasons": missing_preflight,
        "external_required": [
            "Owner-signierte Portfolio-Limits mit Git-SHA und Umgebung.",
            "Staging-/Shadow-Portfolio-Drill mit fehlendem/stalem Snapshot, Exposure-, Korrelation- und Family-Limit.",
            "Backtest-, Walk-forward-, Paper-, Shadow- und Slippage/Funding-Reports pro Asset-Klasse.",
            "Shadow-Burn-in-Report mit Divergenz-Auswertung und Operator-/Owner-Freigabe.",
        ],
        "notes": [
            "Dieser Report erzeugt synthetische Repo-Evidence ohne echte Orders und ohne Secrets.",
            "Implementierte Gates sind nicht gleich verified; private Live bleibt bis externer Evidence NO_GO.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Portfolio Strategy Evidence Report",
        "",
        "Status: synthetischer Fail-closed-Nachweis fuer Portfolio-Risk und Strategy-Validation pro Asset-Klasse.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private-Live-Entscheidung: `{payload['private_live_decision']}`",
        f"- Full-Autonomous-Live: `{payload['full_autonomous_live']}`",
        f"- Externe Evidence: `{payload['external_evidence_assessment']['status']}`",
        f"- Fehlende Portfolio-Blockgruende: `{len(payload['missing_portfolio_block_reasons'])}`",
        f"- Fehlende Strategy-Blockgruende: `{len(payload['missing_strategy_block_reasons'])}`",
        f"- Fehlende Multi-Asset-Strategy-Gruende: `{len(payload['missing_multi_asset_strategy_reasons'])}`",
        f"- Fehlende Live-Preflight-Gruende: `{len(payload['missing_live_preflight_reasons'])}`",
        "",
        "## Portfolio-Risk-Coverage",
        "",
        "- Abgedeckt: "
        + (", ".join(f"`{item}`" for item in payload["covered_portfolio_block_reasons"]) or "-"),
        "- Fehlend: " + (", ".join(f"`{item}`" for item in payload["missing_portfolio_block_reasons"]) or "-"),
        "",
    ]
    for row in payload["portfolio_scenarios"]:
        lines.append(f"- `{row['id']}`: blockiert=`{row['blocks_live']}`, Gruende={', '.join(row['block_reasons']) or '-'}")

    lines.extend(["", "## Strategy-Asset-Evidence", ""])
    for row in payload["strategy_asset_scenarios"]:
        lines.append(
            f"- `{row['strategy_id']}`/`{row['asset_symbol']}`: blockiert=`{row['blocks_live']}`, "
            f"Gruende={', '.join(row['block_reasons']) or '-'}"
        )

    lines.extend(["", "## Multi-Asset-Strategy-Evidence", ""])
    for row in payload["multi_asset_strategy_scenarios"]:
        lines.append(
            f"- `{row['strategy_id']}`/`{row['asset_symbol']}`: verdict=`{row['verdict']}`, "
            f"Gruende={', '.join(row['block_reasons_de']) or '-'}"
        )

    lines.extend(["", "## Externe Evidence", ""])
    lines.append(
        "- Assessment: "
        f"`{payload['external_evidence_assessment']['status']}`; "
        "Fehler="
        + (", ".join(f"`{item}`" for item in payload["external_evidence_assessment"]["failures"]) or "-")
    )
    lines.extend(["", "## Erforderlich vor Private Live", ""])
    lines.extend(f"- {item}" for item in payload["external_required"])
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-asset-input", type=Path, default=DEFAULT_STRATEGY_ASSET_INPUT)
    parser.add_argument("--multi-asset-input", type=Path, default=DEFAULT_MULTI_ASSET_INPUT)
    parser.add_argument("--external-evidence-json", type=Path, default=DEFAULT_EXTERNAL_TEMPLATE)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_evidence_template(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"portfolio_strategy_evidence_report: wrote template {args.write_template}")
        return 0

    payload = build_report_payload(
        strategy_asset_input=args.strategy_asset_input,
        multi_asset_input=args.multi_asset_input,
        external_evidence_json=args.external_evidence_json,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")

    internal_missing = (
        payload["missing_portfolio_block_reasons"]
        + payload["missing_strategy_block_reasons"]
        + payload["missing_multi_asset_strategy_reasons"]
        + payload["missing_live_preflight_reasons"]
    )
    print(
        "portfolio_strategy_evidence_report: "
        f"portfolio={len(payload['portfolio_scenarios'])} "
        f"strategy_asset={len(payload['strategy_asset_scenarios'])} "
        f"multi_asset={len(payload['multi_asset_strategy_scenarios'])} "
        f"internal_missing={len(internal_missing)} "
        f"external_status={payload['external_evidence_assessment']['status']}"
    )
    if args.strict and internal_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
