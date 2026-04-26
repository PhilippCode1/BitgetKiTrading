#!/usr/bin/env python3
"""Kombinierte Evidence fuer Audit, Forensics, Replay und Admin/Main-Console-Security."""

from __future__ import annotations

import argparse
import importlib.util
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

from scripts.admin_gateway_security_report import build_report_payload as build_admin_gateway_payload  # noqa: E402
from scripts.main_console_safety_audit_report import build_report_payload as build_main_console_payload  # noqa: E402
from shared_py.audit_contracts import validate_private_audit_event  # noqa: E402
from shared_py.replay_summary import build_replay_summary  # noqa: E402

DEFAULT_EXTERNAL_TEMPLATE = ROOT / "docs" / "production_10_10" / "audit_forensics_replay_evidence.template.json"

EXTERNAL_SCHEMA_VERSION = 1

SECRET_LIKE_KEYS = ("api_key", "secret", "passphrase", "token", "password", "authorization", "private_key")


def _load_analyze_private_audit_forensics():
    path = ROOT / "tools" / "check_private_audit_forensics.py"
    name = "_bitget_check_private_audit_forensics"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # Dataclasses/Pydantic erwarten __module__ in sys.modules bei dynamic load.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.analyze_private_audit_forensics


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
        "reviewed_by": "CHANGE_ME_EXTERNAL_OR_OWNER",
        "reviewed_at": "CHANGE_ME_ISO8601",
        "environment": "CHANGE_ME_STAGING_OR_SHADOW",
        "git_sha": "CHANGE_ME_GIT_SHA",
        "staging_replay": {
            "performed": False,
            "window_start": "CHANGE_ME_ISO8601",
            "window_end": "CHANGE_ME_ISO8601",
            "trace_ids_sampled": [],
            "signal_risk_exchange_chain_verified": False,
            "live_orders_during_replay": False,
            "report_uri": "CHANGE_ME_STAGING_REPLAY_REPORT_URI",
        },
        "ledger": {
            "storage_durable": False,
            "append_only_policy": False,
            "retention_days": None,
            "export_uri": "CHANGE_ME_LEDGER_EXPORT_URI",
        },
        "forensics": {
            "searchable_by_trace": False,
            "operator_summary_de_available": False,
            "incident_drill_reference": "CHANGE_ME_INCIDENT_DRILL_URI",
        },
        "safety": {
            "secrets_redacted": True,
            "owner_signoff": False,
            "real_orders_possible": False,
        },
    }


def _missing_or_template(value: Any) -> bool:
    return value is None or value == "" or value == [] or str(value).startswith("CHANGE_ME")


def _secret_surface_issues(value: Any, path: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if any(marker in str(key).lower() for marker in SECRET_LIKE_KEYS):
                if isinstance(child, str) and child not in {"", "REDACTED", "[REDACTED]"}:
                    issues.append(f"{child_path}_not_redacted")
            issues.extend(_secret_surface_issues(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_secret_surface_issues(child, f"{path}[{index}]"))
    return issues


def assess_external_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != EXTERNAL_SCHEMA_VERSION:
        failures.append("schema_version_unbekannt")
    if payload.get("status") != "verified":
        failures.append("external_status_nicht_verified")
    for key in ("reviewed_by", "reviewed_at", "environment", "git_sha"):
        if _missing_or_template(payload.get(key)):
            failures.append(f"{key}_fehlt")

    staging = payload.get("staging_replay") or {}
    if staging.get("performed") is not True:
        failures.append("staging_replay_nicht_durchgefuehrt")
    if staging.get("live_orders_during_replay") is not False:
        failures.append("staging_replay_darf_keine_live_orders_haben")
    if staging.get("signal_risk_exchange_chain_verified") is not True:
        failures.append("signal_risk_exchange_chain_nicht_belegt")
    for key in ("window_start", "window_end", "report_uri"):
        if _missing_or_template(staging.get(key)):
            failures.append(f"staging_replay_{key}_fehlt")
    if not isinstance(staging.get("trace_ids_sampled"), list) or len(staging.get("trace_ids_sampled") or []) == 0:
        failures.append("trace_ids_sampled_fehlt")

    ledger = payload.get("ledger") or {}
    for key in ("storage_durable", "append_only_policy"):
        if ledger.get(key) is not True:
            failures.append(f"ledger_{key}_nicht_belegt")
    if int(ledger.get("retention_days") or 0) <= 0:
        failures.append("ledger_retention_fehlt")
    if _missing_or_template(ledger.get("export_uri")):
        failures.append("ledger_export_uri_fehlt")

    forensics = payload.get("forensics") or {}
    if forensics.get("searchable_by_trace") is not True:
        failures.append("forensics_searchable_by_trace_fehlt")
    if forensics.get("operator_summary_de_available") is not True:
        failures.append("forensics_operator_summary_de_fehlt")
    if _missing_or_template(forensics.get("incident_drill_reference")):
        failures.append("forensics_incident_drill_fehlt")

    safety = payload.get("safety") or {}
    if safety.get("secrets_redacted") is not True:
        failures.append("safety_secrets_redacted_fehlt")
    if safety.get("owner_signoff") is not True:
        failures.append("safety_owner_signoff_fehlt")
    if safety.get("real_orders_possible") is not False:
        failures.append("safety_real_orders_possible_muss_false_sein")

    failures.extend(_secret_surface_issues(payload))
    return {
        "status": "PASS" if not failures else "FAIL",
        "external_required": bool(failures),
        "failures": list(dict.fromkeys(failures)),
    }


def _minimal_valid_audit_event() -> dict[str, Any]:
    return {
        "event_id": "audit-forensics-replay-synthetic-1",
        "event_type": "private_decision_audit",
        "timestamp": _now(),
        "git_sha": _git_sha(),
        "service": "synthetic",
        "asset_symbol": "BTCUSDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "decision_type": "order_decision",
        "decision": "do_not_trade",
        "reason_codes": ["synthetic_replay_check"],
        "reason_text_de": "Synthetischer Audit-Event fuer Evidence-Report; keine echten Orders.",
        "risk_tier": "RISK_TIER_1_MAJOR_LIQUID",
        "liquidity_tier": "LIQUIDITY_TIER_1",
        "data_quality_status": "data_ok",
        "exchange_truth_status": "ok",
        "reconcile_status": "ok",
        "operator_context": "system",
        "trace_id": "trace-synthetic-audit-1",
        "correlation_id": "corr-synthetic-audit-1",
        "no_secrets_confirmed": True,
    }


def build_report_payload(
    *, external_evidence_json: Path = DEFAULT_EXTERNAL_TEMPLATE
) -> dict[str, Any]:
    analyze = _load_analyze_private_audit_forensics()
    private_audit_surface = analyze()

    main_payload = build_main_console_payload()
    admin_payload = build_admin_gateway_payload()

    audit_validation = validate_private_audit_event(_minimal_valid_audit_event())

    complete_trace = {
        "steps": {
            "signal": {"strength": 0.5},
            "risk": {"reason_codes": ["test"]},
            "exchange": {"exchange_truth_status": "ok"},
        },
        "llm_explanation_only": False,
    }
    incomplete_trace = {
        "steps": {
            "signal": {"strength": 0.2},
        },
    }
    llm_only_trace = {**complete_trace, "llm_explanation_only": True}

    replay_rows = {
        "complete": build_replay_summary(complete_trace),
        "incomplete": build_replay_summary(incomplete_trace),
        "llm_explanation_flag": build_replay_summary(llm_only_trace),
    }

    external_payload = json.loads(external_evidence_json.read_text(encoding="utf-8"))
    external_assessment = assess_external_evidence(external_payload)

    internal_issues: list[str] = []
    if not private_audit_surface.get("ok"):
        internal_issues.append("private_audit_forensics_checker_failed")
    if main_payload.get("missing_visible_gates") or main_payload.get("blocking_failures") or not main_payload.get("secret_safe"):
        internal_issues.append("main_console_safety_audit_incomplete")
    if admin_payload.get("missing_required_scenarios") or admin_payload.get("failures") or not admin_payload.get("secret_safe"):
        internal_issues.append("admin_gateway_security_incomplete")
    if not audit_validation.valid:
        internal_issues.append("minimal_audit_event_invalid")
    if not replay_rows["complete"].get("replay_sufficient"):
        internal_issues.append("replay_complete_sample_not_sufficient")
    if replay_rows["incomplete"].get("replay_sufficient"):
        internal_issues.append("replay_incomplete_sample_should_fail")

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "private_audit_forensics_surface": private_audit_surface,
        "main_console_safety_embed": {
            "private_live_decision": main_payload.get("private_live_decision"),
            "missing_visible_gates": main_payload.get("missing_visible_gates"),
            "blocking_failures": main_payload.get("blocking_failures"),
            "secret_safe": main_payload.get("secret_safe"),
        },
        "admin_gateway_security_embed": {
            "private_live_decision": admin_payload.get("private_live_decision"),
            "missing_required_scenarios": admin_payload.get("missing_required_scenarios"),
            "failures": admin_payload.get("failures"),
            "secret_safe": admin_payload.get("secret_safe"),
        },
        "minimal_order_audit_validation": {
            "valid": audit_validation.valid,
            "errors": audit_validation.errors,
        },
        "replay_scenarios": replay_rows,
        "external_evidence_assessment": external_assessment,
        "internal_issues": internal_issues,
        "external_required": [
            "Staging-/Shadow-Replay mit nachvollziehbarer Signal-Risk-Exchange-Kette und ohne Live-Orders.",
            "Dauerhaftes Audit-Ledger mit Retention, Export und Tamper-Nachweis extern.",
            "Forensics-Suche nach trace_id/correlation_id und deutscher Operator-Zusammenfassung in Incidents.",
            "Owner-Signoff fuer Audit-/Replay-Prozess vor privatem Live-Go.",
        ],
        "notes": [
            "Dieser Report bündelt nur repo-lokale, synthetische Checks; kein echter Staging- oder Prod-Lauf.",
            "private_live_allowed bleibt NO_GO, bis externe verified Evidence und Owner-Signoff vorliegen.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    ext = payload["external_evidence_assessment"]
    lines = [
        "# Audit Forensics Replay Security Evidence Report",
        "",
        "Status: kombinierter Nachweis fuer Audit/Forensics, Replay, Main-Console-Safety und Admin-Gateway.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Private-Audit-Checker ok: `{payload['private_audit_forensics_surface'].get('ok')}`",
        f"- Externe Evidence: `{ext['status']}`",
        f"- Interne Issues: `{len(payload['internal_issues'])}`",
        "",
        "## Interne Pruefungen (Repo)",
        "",
        f"- `check_private_audit_forensics`: error_count={payload['private_audit_forensics_surface'].get('error_count')}",
        f"- Main Console: missing_gates={len(payload['main_console_safety_embed']['missing_visible_gates'] or [])} "
        f"blocking_failures={len(payload['main_console_safety_embed']['blocking_failures'] or [])}",
        f"- Admin Gateway: missing_scenarios={len(payload['admin_gateway_security_embed']['missing_required_scenarios'] or [])} "
        f"failures={len(payload['admin_gateway_security_embed']['failures'] or [])}",
        f"- Minimales Order-Audit-Event valide: `{payload['minimal_order_audit_validation']['valid']}`",
        "",
        "## Replay",
        "",
    ]
    for key, value in payload["replay_scenarios"].items():
        suff = value.get("replay_sufficient")
        lines.append(f"- `{key}`: replay_sufficient=`{suff}` missing={value.get('missing_steps')}")
    lines.extend(
        [
            "",
            "## Externe Evidence",
            "",
            f"- Status: `{ext['status']}`",
            "- Fehler: " + (", ".join(f"`{item}`" for item in ext["failures"]) or "-"),
            "",
            "## Erforderlich extern",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["external_required"])
    lines.extend(["", "## Interne Issues", ""])
    lines.extend(f"- `{item}`" for item in payload["internal_issues"] or ["-"])
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-evidence-json", type=Path, default=DEFAULT_EXTERNAL_TEMPLATE)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 wenn interne Checks fehlschlagen (Subreports, Replay, Audit-Event, private-audit-surface).",
    )
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Zusaetzlich: externe Evidence muss assess_external_evidence PASS erfuellen (fuer verifizierte JSON-Dateien).",
    )
    args = parser.parse_args(argv)

    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_evidence_template(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"audit_forensics_replay_evidence_report: wrote template {args.write_template}")
        return 0

    payload = build_report_payload(external_evidence_json=args.external_evidence_json)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")

    print(
        "audit_forensics_replay_evidence_report: "
        f"internal_issues={len(payload['internal_issues'])} "
        f"external={payload['external_evidence_assessment']['status']}"
    )
    if args.strict and payload["internal_issues"]:
        return 1
    if args.strict_external and payload["external_evidence_assessment"]["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
