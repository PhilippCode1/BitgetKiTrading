#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.live_preflight import (  # noqa: E402
    LivePreflightContext,
    build_live_preflight_reasons_de,
    evaluate_live_preflight,
)

DEFAULT_REPORT = ROOT / "reports" / "live_broker_preflight_matrix.md"
FAIL_CLOSED_EVIDENCE_SCHEMA_VERSION = "live-broker-fail-closed-evidence-v1"
DEFAULT_EVIDENCE_TEMPLATE = ROOT / "docs" / "production_10_10" / "live_broker_fail_closed_evidence.template.json"
SECRET_LIKE_KEYS = ("database_url", "redis_url", "dsn", "password", "secret", "token", "api_key", "authorization")

REQUIRED_BLOCKING_REASONS = (
    "execution_mode_not_live",
    "live_trade_enable_false",
    "owner_approval_missing",
    "asset_not_in_catalog",
    "asset_status_not_ok",
    "asset_not_live_allowed",
    "instrument_contract_missing",
    "instrument_metadata_stale",
    "data_quality_not_pass",
    "liquidity_not_pass",
    "slippage_too_high",
    "risk_tier_not_live_allowed",
    "order_sizing_not_safe",
    "portfolio_risk_not_safe",
    "strategy_evidence_missing_or_invalid",
    "bitget_readiness_not_ok",
    "reconcile_not_ok",
    "kill_switch_active",
    "safety_latch_active",
    "unknown_order_state_active",
    "account_snapshot_stale",
    "idempotency_key_missing",
    "audit_context_missing",
)


def build_external_evidence_template() -> dict[str, object]:
    return {
        "schema_version": FAIL_CLOSED_EVIDENCE_SCHEMA_VERSION,
        "environment": "staging",
        "execution_mode": "shadow",
        "drill_started_at": "",
        "drill_completed_at": "",
        "git_sha": "",
        "operator": "",
        "evidence_reference": "",
        "preflight_matrix_passed": False,
        "all_required_blocking_reasons_covered": False,
        "provider_error_blocks_submit": False,
        "redis_missing_blocks_live": False,
        "database_missing_blocks_live": False,
        "exchange_truth_missing_blocks_submit": False,
        "public_api_timeout_blocks_submit": False,
        "private_api_timeout_blocks_submit": False,
        "stale_market_data_blocks_submit": False,
        "unknown_instrument_blocks_submit": False,
        "risk_context_missing_blocks_submit": False,
        "operator_release_missing_blocks_submit": False,
        "shadow_match_missing_blocks_submit": False,
        "reconcile_fail_blocks_submit": False,
        "kill_switch_blocks_submit": False,
        "safety_latch_blocks_submit": False,
        "idempotency_missing_blocks_submit": False,
        "audit_context_missing_blocks_submit": False,
        "warning_defaults_block_live": False,
        "all_green_control_no_exchange_submit": False,
        "audit_trail_verified": False,
        "alert_delivery_verified": False,
        "main_console_gate_state_verified": False,
        "live_write_allowed_during_drill": False,
        "real_exchange_order_sent": False,
        "owner_signoff": False,
        "database_url": "[REDACTED]",
        "redis_url": "[REDACTED]",
        "authorization": "[REDACTED]",
        "notes_de": "Template: echten Staging-/Shadow-Live-Broker-Fail-Closed-Drill extern ausfuehren; Secrets niemals im Repo speichern.",
    }


def secret_surface_issues(payload: dict[str, object]) -> list[str]:
    issues: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def assess_external_evidence(payload: dict[str, object] | None) -> tuple[str, list[str], list[str]]:
    if not payload:
        return "FAIL", ["live_broker_fail_closed_evidence_missing"], []
    blockers: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != FAIL_CLOSED_EVIDENCE_SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if payload.get("environment") not in {"staging", "shadow", "production_shadow"}:
        blockers.append("environment_invalid")
    if payload.get("execution_mode") not in {"shadow", "paper"}:
        blockers.append("execution_mode_not_non_live")
    for key, code in (
        ("drill_started_at", "drill_started_at_missing"),
        ("drill_completed_at", "drill_completed_at_missing"),
        ("git_sha", "git_sha_missing"),
        ("operator", "operator_missing"),
        ("evidence_reference", "evidence_reference_missing"),
    ):
        if not str(payload.get(key) or "").strip():
            blockers.append(code)
    required_true = (
        ("preflight_matrix_passed", "preflight_matrix_not_passed"),
        ("all_required_blocking_reasons_covered", "required_blocking_reasons_not_covered"),
        ("provider_error_blocks_submit", "provider_error_not_blocking"),
        ("redis_missing_blocks_live", "redis_missing_not_blocking"),
        ("database_missing_blocks_live", "database_missing_not_blocking"),
        ("exchange_truth_missing_blocks_submit", "exchange_truth_missing_not_blocking"),
        ("public_api_timeout_blocks_submit", "public_api_timeout_not_blocking"),
        ("private_api_timeout_blocks_submit", "private_api_timeout_not_blocking"),
        ("stale_market_data_blocks_submit", "stale_market_data_not_blocking"),
        ("unknown_instrument_blocks_submit", "unknown_instrument_not_blocking"),
        ("risk_context_missing_blocks_submit", "risk_context_missing_not_blocking"),
        ("operator_release_missing_blocks_submit", "operator_release_missing_not_blocking"),
        ("shadow_match_missing_blocks_submit", "shadow_match_missing_not_blocking"),
        ("reconcile_fail_blocks_submit", "reconcile_fail_not_blocking"),
        ("kill_switch_blocks_submit", "kill_switch_not_blocking"),
        ("safety_latch_blocks_submit", "safety_latch_not_blocking"),
        ("idempotency_missing_blocks_submit", "idempotency_missing_not_blocking"),
        ("audit_context_missing_blocks_submit", "audit_context_missing_not_blocking"),
        ("warning_defaults_block_live", "warning_defaults_not_blocking_live"),
        ("all_green_control_no_exchange_submit", "all_green_control_sent_exchange_submit"),
        ("audit_trail_verified", "audit_trail_not_verified"),
        ("alert_delivery_verified", "alert_delivery_not_verified"),
        ("main_console_gate_state_verified", "main_console_gate_state_not_verified"),
    )
    for key, code in required_true:
        if payload.get(key) is not True:
            blockers.append(code)
    if payload.get("live_write_allowed_during_drill") is not False:
        blockers.append("live_write_allowed_during_drill")
    if payload.get("real_exchange_order_sent") is not False:
        blockers.append("real_exchange_order_sent")
    if payload.get("owner_signoff") is not True:
        warnings.append("owner_signoff_missing_external_required")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return status, blockers, warnings


def _base_context() -> LivePreflightContext:
    return LivePreflightContext(
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
        portfolio_risk_ok=True,
        strategy_evidence_ok=True,
        bitget_readiness_ok=True,
        reconcile_ok=True,
        kill_switch_active=False,
        safety_latch_active=False,
        unknown_order_state=False,
        account_snapshot_fresh=True,
        idempotency_key="synthetic-idempotency-key",
        audit_context_present=True,
        warning_policy_allows_live={},
        checked_at="synthetic-preflight-check",
    )


def _ctx(**overrides: object) -> LivePreflightContext:
    return LivePreflightContext(**{**_base_context().__dict__, **overrides})  # type: ignore[arg-type]


SCENARIOS: tuple[tuple[str, LivePreflightContext, str], ...] = (
    ("execution_mode_not_live", _ctx(execution_mode_live=False), "Nicht-live Modus blockiert Live-Submit."),
    ("live_trade_enable_false", _ctx(live_trade_enable=False), "LIVE_TRADE_ENABLE=false blockiert."),
    ("owner_approval_missing", _ctx(owner_approved=False), "Owner-Freigabe fehlt."),
    ("asset_not_in_catalog", _ctx(asset_in_catalog=False), "Unbekanntes Asset blockiert."),
    ("asset_status_not_ok", _ctx(asset_status_ok=False), "Delisted/suspended/unknown blockiert."),
    ("asset_not_live_allowed", _ctx(asset_live_allowed=False), "Asset ist nicht live freigegeben."),
    ("instrument_contract_missing", _ctx(instrument_contract_complete=False), "Instrument-Contract fehlt."),
    ("instrument_metadata_stale", _ctx(instrument_metadata_fresh=False), "Metadaten stale."),
    ("data_quality_not_pass", _ctx(data_quality_status="stale"), "Stale Datenqualitaet blockiert."),
    ("liquidity_not_pass", _ctx(liquidity_status="missing"), "Fehlende Liquiditaet blockiert."),
    ("slippage_too_high", _ctx(slippage_ok=False), "Slippage-Gate blockiert."),
    ("risk_tier_not_live_allowed", _ctx(risk_tier_live_allowed=False), "Risk-Tier nicht livefaehig."),
    ("order_sizing_not_safe", _ctx(order_sizing_ok=False), "Order-Sizing unsicher."),
    ("portfolio_risk_not_safe", _ctx(portfolio_risk_ok=False), "Portfolio-Risk unsicher."),
    ("strategy_evidence_missing_or_invalid", _ctx(strategy_evidence_ok=False), "Strategie-Evidence fehlt."),
    ("bitget_readiness_not_ok", _ctx(bitget_readiness_ok=False), "Bitget-Readiness fehlt."),
    ("reconcile_not_ok", _ctx(reconcile_ok=False), "Reconcile nicht ok."),
    ("kill_switch_active", _ctx(kill_switch_active=True), "Kill-Switch aktiv."),
    ("safety_latch_active", _ctx(safety_latch_active=True), "Safety-Latch aktiv."),
    ("unknown_order_state_active", _ctx(unknown_order_state=True), "Unklarer Order-State aktiv."),
    ("account_snapshot_stale", _ctx(account_snapshot_fresh=False), "Account-Snapshot stale."),
    ("idempotency_key_missing", _ctx(idempotency_key=None), "Idempotency-Key fehlt."),
    ("audit_context_missing", _ctx(audit_context_present=False), "Audit-Context fehlt."),
    ("all_green_control", _base_context(), "Kontrollfall ohne echten Submit."),
)


def scenario_results() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for scenario_id, context, description in SCENARIOS:
        decision = evaluate_live_preflight(context)
        expected_reason = None if scenario_id == "all_green_control" else scenario_id
        expected_blocked = scenario_id != "all_green_control"
        rows.append(
            {
                "id": scenario_id,
                "description_de": description,
                "expected_blocked": expected_blocked,
                "passed": decision.passed,
                "submit_allowed": decision.submit_allowed,
                "blocking_reasons": decision.blocking_reasons,
                "warning_reasons": decision.warning_reasons,
                "missing_gates": decision.missing_gates,
                "german_reasons": build_live_preflight_reasons_de(decision),
                "ok": (
                    decision.submit_allowed is False
                    and expected_reason in decision.blocking_reasons
                )
                if expected_blocked and expected_reason
                else decision.submit_allowed is True and not decision.blocking_reasons,
            }
        )
    return rows


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "live_broker_multi_asset_preflight.md"
    module = ROOT / "shared" / "python" / "src" / "shared_py" / "live_preflight.py"
    sec_test = ROOT / "tests" / "security" / "test_live_broker_multi_asset_preflight.py"
    lb_test = ROOT / "tests" / "live_broker" / "test_live_preflight_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_live_broker_preflight.py"
    main_console = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
    live_broker_service = ROOT / "services" / "live-broker" / "src" / "live_broker" / "orders" / "service.py"

    for path, code, message in (
        (doc, "doc_missing", "Live-Preflight-Doku fehlt."),
        (module, "module_missing", "live_preflight.py fehlt."),
        (sec_test, "security_test_missing", "Security-Tests fehlen."),
        (lb_test, "live_broker_test_missing", "Live-Broker-Contract-Tests fehlen."),
        (tool_test, "tool_test_missing", "Tool-Tests fehlen."),
        (live_broker_service, "live_broker_missing", "Live-Broker-Service fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})

    if no_go.is_file():
        text = no_go.read_text(encoding="utf-8").lower()
        if "preflight" not in text:
            issues.append({"severity": "error", "code": "no_go_preflight_missing", "message": "No-Go-Regeln erwaehnen Preflight nicht.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_doc_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    if main_console.is_file():
        text = main_console.read_text(encoding="utf-8").lower()
        if "preflight" not in text:
            issues.append({"severity": "error", "code": "main_console_preflight_missing", "message": "Main-Console-Doku erwaehnt Preflight-Blockgruende nicht.", "path": str(main_console)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console)})

    results = scenario_results()
    covered = {
        reason
        for row in results
        for reason in row["blocking_reasons"]
        if isinstance(reason, str)
    }
    for reason in REQUIRED_BLOCKING_REASONS:
        if reason not in covered:
            issues.append(
                {
                    "severity": "error",
                    "code": "preflight_reason_not_covered",
                    "message": f"Blockgrund wird nicht in der Szenario-Matrix belegt: {reason}",
                    "path": str(module),
                }
            )
    for row in results:
        if row["ok"] is not True:
            issues.append(
                {
                    "severity": "error",
                    "code": "preflight_scenario_failed",
                    "message": f"Szenario {row['id']} liefert nicht die erwartete Fail-closed-Entscheidung.",
                    "path": str(module),
                }
            )

    error_count = sum(1 for item in issues if item["severity"] == "error")
    return {
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": 0,
        "issues": issues,
        "scenario_count": len(results),
        "covered_blocking_reasons": sorted(covered),
        "scenarios": results,
    }


def render_markdown(payload: dict[str, object]) -> str:
    scenarios = payload.get("scenarios")
    scenario_rows = scenarios if isinstance(scenarios, list) else []
    lines = [
        "# Live-Broker Preflight Matrix",
        "",
        "Status: synthetischer, repo-lokaler Fail-closed-Nachweis ohne echte Orders und ohne Secrets.",
        "",
        "## Summary",
        "",
        f"- OK: `{str(payload.get('ok')).lower()}`",
        f"- Szenarien: `{payload.get('scenario_count')}`",
        f"- Fehler: `{payload.get('error_count')}`",
        "",
        "## Szenarien",
        "",
        "| Szenario | Erwartung | Submit erlaubt | Blockgruende | Deutsche Operator-Gruende |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in scenario_rows:
        if not isinstance(row, dict):
            continue
        blocking = ", ".join(f"`{item}`" for item in row.get("blocking_reasons", [])) or "-"
        german = "<br>".join(str(item) for item in row.get("german_reasons", [])) or "-"
        expected = "block" if row.get("expected_blocked") else "allow"
        submit = "ja" if row.get("submit_allowed") else "nein"
        lines.append(
            f"| `{row.get('id')}` | `{expected}` | `{submit}` | {blocking} | {german} |"
        )
    lines.extend(["", "## Bewertung", ""])
    if payload.get("ok") is True:
        lines.append("- Alle synthetischen Pflichtgate-Szenarien blockieren fail-closed; der Kontrollfall bleibt submit-fahig.")
    else:
        lines.append("- Mindestens ein Pflichtgate-Szenario ist nicht belegt oder nicht fail-closed.")
    lines.append("- Dieser Report ersetzt keine externe Shadow-, Bitget-, Restore- oder Owner-Evidence.")
    lines.append("")
    return "\n".join(lines)


def render_external_markdown(
    payload: dict[str, object],
    status: str,
    blockers: list[str],
    warnings: list[str],
    secret_issues: list[str],
) -> str:
    lines = [
        "# Live-Broker Fail-Closed Evidence Check",
        "",
        "Status: prueft externen Live-Broker-Fail-Closed-Nachweis ohne echte Secrets und ohne echte Orders.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Execution Mode: `{payload.get('execution_mode')}`",
        f"- Git SHA: `{payload.get('git_sha') or 'missing'}`",
        f"- Operator: `{payload.get('operator') or 'missing'}`",
        f"- Ergebnis: `{status}`",
        "",
        "## Blocker",
    ]
    lines.extend(f"- `{item}`" for item in blockers)
    if not blockers:
        lines.append("- Keine technischen Blocker.")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in warnings)
    if not warnings:
        lines.append("- Keine Warnings.")
    lines.extend(["", "## Secret-Surface"])
    lines.extend(f"- `{item}`" for item in secret_issues)
    if not secret_issues:
        lines.append("- Keine unredigierten Secret-Felder erkannt.")
    lines.extend(
        [
            "",
            "## Einordnung",
            "",
            "- Repo-lokale Preflight-Matrix ist Code-Evidence, aber keine private Live-Freigabe.",
            "- Live bleibt `NO_GO`, bis Provider-/Redis-/DB-/Timeout-/Exchange-Truth-Failures, Audit, Alert und Main-Console-State extern belegt sind.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Live-Broker-Multi-Asset-Preflight-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", type=Path)
    parser.add_argument("--evidence-json", type=Path)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_evidence_template(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote template: {args.write_template}")
        return 0
    if args.evidence_json:
        loaded = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Evidence root muss ein JSON-Objekt sein.")
        status, blockers, warnings = assess_external_evidence(loaded)
        secret_issues = secret_surface_issues(loaded)
        payload = {
            "ok": status == "PASS" and not secret_issues,
            "status": status,
            "blockers": blockers + secret_issues,
            "warnings": warnings,
        }
        if args.write_report:
            args.write_report.parent.mkdir(parents=True, exist_ok=True)
            args.write_report.write_text(
                render_external_markdown(loaded, status, blockers, warnings, secret_issues),
                encoding="utf-8",
            )
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        elif not args.write_report:
            print(render_external_markdown(loaded, status, blockers, warnings, secret_issues))
        return 1 if args.strict and not payload["ok"] else 0
    payload = analyze()
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(render_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_live_broker_preflight: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']}"
        )
        for item in payload["issues"]:
            print(f"{item['severity'].upper()} {item['code']}: {item['message']} [{item['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
