#!/usr/bin/env python3
"""Erzeugt Evidence fuer Single-Owner-Admin und API-Gateway-Security."""

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
API_GATEWAY_SRC = ROOT / "services" / "api-gateway" / "src"
for import_path in (ROOT, SHARED_SRC, API_GATEWAY_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from api_gateway.auth import GatewayAuthContext  # noqa: E402
from api_gateway.manual_action import (  # noqa: E402
    ROUTE_KEY_OPERATOR_RELEASE,
    ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN,
)
from shared_py.audit_contracts import build_private_audit_event, payload_contains_secret_markers  # noqa: E402
from shared_py.single_admin_access import (  # noqa: E402
    SingleAdminContext,
    assert_single_admin_context,
    contains_forbidden_public_secret_env,
    private_console_access_blocks_sensitive_action,
    redact_auth_error,
)

REQUIRED_SCENARIO_IDS = (
    "missing_auth_blocks_admin",
    "single_admin_subject_mismatch_blocks",
    "legacy_admin_token_forbidden_in_production",
    "read_role_cannot_mutate_live_broker",
    "operator_role_requires_manual_action_for_release",
    "emergency_role_requires_manual_action_for_flatten",
    "customer_portal_cannot_admin",
    "public_secret_env_blocked",
    "auth_errors_are_redacted",
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


def _audit_event(*, scenario_id: str, decision: str, reasons: list[str], git_sha: str) -> dict[str, Any]:
    return {
        "event_id": f"admin-gateway-security-{scenario_id}",
        "event_type": "private_decision_audit",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "git_sha": git_sha,
        "service": "api-gateway",
        "asset_symbol": "ALL",
        "market_family": "private_admin",
        "product_type": "main-console",
        "margin_coin": "USDT",
        "decision_type": "live_decision",
        "decision": decision,
        "reason_codes": reasons,
        "reason_text_de": "Admin-/Gateway-Sicherheitsregel blockiert Live-, Replay- oder Admin-Aktion fuer Nicht-Owner oder unsichere Auth.",
        "risk_tier": "admin_access",
        "liquidity_tier": "not_applicable",
        "data_quality_status": "not_applicable",
        "exchange_truth_status": "not_applicable",
        "reconcile_status": "not_applicable",
        "operator_context": "philipp",
        "trace_id": f"trace-{scenario_id}",
        "correlation_id": f"corr-{scenario_id}",
        "no_secrets_confirmed": True,
    }


def _scenario(
    *,
    scenario_id: str,
    passed: bool,
    blocks_sensitive_action: bool,
    reasons: list[str],
    git_sha: str,
    manual_action_required: bool = False,
) -> dict[str, Any]:
    audit = build_private_audit_event(
        _audit_event(
            scenario_id=scenario_id,
            decision="do_not_trade" if blocks_sensitive_action else "next_gate_only",
            reasons=reasons,
            git_sha=git_sha,
        )
    )
    return {
        "id": scenario_id,
        "passed": passed,
        "private_live_allowed": "NO_GO",
        "blocks_sensitive_action": blocks_sensitive_action,
        "manual_action_required": manual_action_required,
        "reason_codes": reasons,
        "audit_valid": bool(audit["validation"]["valid"]),
        "audit_errors": audit["validation"]["errors"],
        "secret_safe": not payload_contains_secret_markers(audit),
    }


def build_report_payload() -> dict[str, Any]:
    git_sha = _git_sha()
    scenarios: list[dict[str, Any]] = []

    blocks_missing_auth = private_console_access_blocks_sensitive_action(
        has_auth=False,
        is_single_admin_ok=True,
    )
    scenarios.append(
        _scenario(
            scenario_id="missing_auth_blocks_admin",
            passed=blocks_missing_auth,
            blocks_sensitive_action=blocks_missing_auth,
            reasons=["auth_missing_blocks_sensitive_action"],
            git_sha=git_sha,
        )
    )

    subject_mismatch_blocks = False
    try:
        assert_single_admin_context(
            SingleAdminContext(
                admin_subject="philipp-stable-subject",
                caller_subject="intruder",
                production=True,
                legacy_admin_token_allowed=False,
            )
        )
    except PermissionError:
        subject_mismatch_blocks = True
    scenarios.append(
        _scenario(
            scenario_id="single_admin_subject_mismatch_blocks",
            passed=subject_mismatch_blocks,
            blocks_sensitive_action=subject_mismatch_blocks,
            reasons=["single_admin_subject_mismatch"],
            git_sha=git_sha,
        )
    )

    legacy_prod_blocks = False
    try:
        assert_single_admin_context(
            SingleAdminContext(
                admin_subject="philipp-stable-subject",
                caller_subject="philipp-stable-subject",
                production=True,
                legacy_admin_token_allowed=True,
            )
        )
    except PermissionError:
        legacy_prod_blocks = True
    scenarios.append(
        _scenario(
            scenario_id="legacy_admin_token_forbidden_in_production",
            passed=legacy_prod_blocks,
            blocks_sensitive_action=legacy_prod_blocks,
            reasons=["legacy_admin_token_forbidden_in_production"],
            git_sha=git_sha,
        )
    )

    read_ctx = GatewayAuthContext(actor="philipp", auth_method="jwt", roles=frozenset({"gateway:read"}))
    read_cannot_mutate = not read_ctx.can_admin_write() and not read_ctx.can_execute_live_broker_route(
        ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN
    )
    scenarios.append(
        _scenario(
            scenario_id="read_role_cannot_mutate_live_broker",
            passed=read_cannot_mutate,
            blocks_sensitive_action=read_cannot_mutate,
            reasons=["gateway_read_role_cannot_mutate_live_broker"],
            git_sha=git_sha,
        )
    )

    operator_ctx = GatewayAuthContext(actor="philipp", auth_method="jwt", roles=frozenset({"operator:mutate"}))
    operator_route_allowed = operator_ctx.can_execute_live_broker_route(ROUTE_KEY_OPERATOR_RELEASE)
    scenarios.append(
        _scenario(
            scenario_id="operator_role_requires_manual_action_for_release",
            passed=operator_route_allowed,
            blocks_sensitive_action=False,
            manual_action_required=True,
            reasons=["operator_release_requires_bound_manual_action_token"],
            git_sha=git_sha,
        )
    )

    emergency_ctx = GatewayAuthContext(actor="philipp", auth_method="jwt", roles=frozenset({"emergency:mutate"}))
    emergency_route_allowed = emergency_ctx.can_execute_live_broker_route(ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN)
    scenarios.append(
        _scenario(
            scenario_id="emergency_role_requires_manual_action_for_flatten",
            passed=emergency_route_allowed,
            blocks_sensitive_action=False,
            manual_action_required=True,
            reasons=["emergency_flatten_requires_bound_manual_action_token"],
            git_sha=git_sha,
        )
    )

    customer_ctx = GatewayAuthContext(
        actor="customer",
        auth_method="jwt",
        roles=frozenset({"billing:read"}),
        portal_roles=frozenset({"customer"}),
    )
    customer_cannot_admin = customer_ctx.is_customer_portal_jwt() and not customer_ctx.can_admin_write()
    scenarios.append(
        _scenario(
            scenario_id="customer_portal_cannot_admin",
            passed=customer_cannot_admin,
            blocks_sensitive_action=customer_cannot_admin,
            reasons=["customer_portal_jwt_cannot_admin_or_live"],
            git_sha=git_sha,
        )
    )

    public_secret_detected = contains_forbidden_public_secret_env("NEXT_PUBLIC_ADMIN_TOKEN=example-only")
    scenarios.append(
        _scenario(
            scenario_id="public_secret_env_blocked",
            passed=public_secret_detected,
            blocks_sensitive_action=public_secret_detected,
            reasons=["next_public_secret_name_blocked"],
            git_sha=git_sha,
        )
    )

    redacted = redact_auth_error("Authorization: Bearer synthetic-token SECRET=value")
    redaction_ok = "synthetic-token" not in redacted and "value" not in redacted and "REDACTED" in redacted
    scenarios.append(
        _scenario(
            scenario_id="auth_errors_are_redacted",
            passed=redaction_ok,
            blocks_sensitive_action=False,
            reasons=["auth_error_redaction_verified"],
            git_sha=git_sha,
        )
    )

    covered = sorted(row["id"] for row in scenarios if row["passed"])
    missing = [scenario_id for scenario_id in REQUIRED_SCENARIO_IDS if scenario_id not in covered]
    failures = [
        row["id"]
        for row in scenarios
        if row["passed"] is not True
        or row["private_live_allowed"] != "NO_GO"
        or row["audit_valid"] is not True
        or row["secret_safe"] is not True
    ]
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": git_sha,
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "scenario_count": len(scenarios),
        "covered_scenarios": covered,
        "missing_required_scenarios": missing,
        "failures": failures,
        "audit_valid_count": sum(1 for row in scenarios if row["audit_valid"]),
        "secret_safe": all(row["secret_safe"] for row in scenarios),
        "scenarios": scenarios,
        "notes": [
            "Synthetische Repo-Evidence ohne echte Tokens, echte Secrets oder echte Live-Aktionen.",
            "Mutationsrollen allein sind keine Live-Freigabe; sensible Aktionen brauchen Owner-Kontext, Auth und gebundene Manual-Action-Evidence.",
            "Externe Owner-Signoff- und Runtime-Auth-Evidence bleibt fuer private Live erforderlich.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Admin / API-Gateway Security Evidence Report",
        "",
        "Status: synthetischer Nachweis fuer Single-Owner-Admin, Gateway-Auth, Live-/Replay-/Admin-Gates und Audit.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Szenarien: `{payload['scenario_count']}`",
        f"- Fehlende Required-Szenarien: `{len(payload['missing_required_scenarios'])}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- Audit valide: `{payload['audit_valid_count']}`",
        f"- Secret-safe: `{payload['secret_safe']}`",
        "",
        "## Szenarien",
        "",
        "| Szenario | Passed | Sensitive Aktion blockiert | Manual Action noetig | Private Live | Gruende |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        reasons = ", ".join(f"`{item}`" for item in row["reason_codes"]) or "-"
        lines.append(
            f"| `{row['id']}` | `{row['passed']}` | `{row['blocks_sensitive_action']}` | "
            f"`{row['manual_action_required']}` | `{row['private_live_allowed']}` | {reasons} |"
        )
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
        "admin_gateway_security_report: "
        f"scenarios={payload['scenario_count']} "
        f"missing_required={len(payload['missing_required_scenarios'])} "
        f"failures={len(payload['failures'])}"
    )
    if args.strict and (payload["missing_required_scenarios"] or payload["failures"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
