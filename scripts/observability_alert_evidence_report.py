#!/usr/bin/env python3
"""Kombinierter Evidence-Report: Observability/SLO-Doku, Alertmanager/Prometheus-Checks, Alert-Drill-JSON."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALERT_EVIDENCE = ROOT / "docs" / "production_10_10" / "alert_routing_evidence.template.json"
DEFAULT_OBSERVABILITY_EVIDENCE = ROOT / "docs" / "production_10_10" / "observability_slos_evidence.template.json"
ALERTMANAGER_EXAMPLE = ROOT / "infra" / "observability" / "alertmanager.yml.example"
PROMETHEUS_ALERTS = ROOT / "infra" / "observability" / "prometheus-alerts.yml"
OBSERVABILITY_EVIDENCE_SCHEMA = 1

REQUIRED_DOCS: tuple[Path, ...] = (
    ROOT / "docs" / "observability.md",
    ROOT / "OBSERVABILITY_AND_SLOS.md",
    ROOT / "docs" / "observability_slos.md",
    ROOT / "docs" / "production_10_10" / "05_alert_routing_and_incident_drill.md",
)

SECRET_LIKE = ("password", "token", "secret", "api_key", "webhook", "authorization")


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


def _load_verify_alert_routing_mod():
    path = ROOT / "tools" / "verify_alert_routing.py"
    name = f"_bitget_verify_alert_routing_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _missing_or_template(value: Any) -> bool:
    if value is None or value == "" or value == []:
        return True
    s = str(value)
    return s.startswith("CHANGE_ME") or s == "null"


def analyze_observability_doc_surface() -> dict[str, Any]:
    missing: list[str] = []
    for p in REQUIRED_DOCS:
        if not p.is_file():
            missing.append(str(p.relative_to(ROOT)))
    return {
        "ok": not missing,
        "required_count": len(REQUIRED_DOCS),
        "missing_paths": missing,
    }


def build_observability_ops_template() -> dict[str, Any]:
    return {
        "schema_version": OBSERVABILITY_EVIDENCE_SCHEMA,
        "status": "external_required",
        "reviewed_by": "CHANGE_ME_EXTERNAL_OR_OWNER",
        "reviewed_at": "CHANGE_ME_ISO8601",
        "environment": "CHANGE_ME_STAGING_OR_SHADOW",
        "git_sha": "CHANGE_ME_GIT_SHA",
        "grafana": {
            "ops_dashboard_uri": "CHANGE_ME_GRAFANA_URI",
            "sli_dashboard_uri": "CHANGE_ME_GRAFANA_URI",
            "baseline_captured": False,
        },
        "slos": {
            "gateway_availability_slo_verified": False,
            "system_health_p95_slo_verified": False,
            "data_freshness_slo_verified": False,
            "live_safety_exposure_slo_verified": False,
        },
        "operations": {
            "on_call_path_documented": False,
            "incident_response_drill_reference": "CHANGE_ME_DRILL_URI",
            "runbook_links_peer_reviewed": False,
        },
        "safety": {
            "no_metrics_secrets_in_repo": True,
            "owner_signoff": False,
        },
    }


def _secret_scan(obj: Any, path: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if any(m in str(k).lower() for m in SECRET_LIKE):
                if isinstance(v, str) and v not in ("", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                    issues.append(f"{p}_not_redacted")
            issues.extend(_secret_scan(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            issues.extend(_secret_scan(v, f"{path}[{i}]"))
    return issues


def assess_observability_ops_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != OBSERVABILITY_EVIDENCE_SCHEMA:
        failures.append("schema_version_unbekannt")
    if payload.get("status") != "verified":
        failures.append("status_nicht_verified")
    for key in ("reviewed_by", "reviewed_at", "environment", "git_sha"):
        if _missing_or_template(payload.get(key)):
            failures.append(f"{key}_fehlt_oder_template")

    g = payload.get("grafana") or {}
    for key in ("ops_dashboard_uri", "sli_dashboard_uri"):
        if _missing_or_template(g.get(key)):
            failures.append(f"grafana_{key}_fehlt")
    if g.get("baseline_captured") is not True:
        failures.append("grafana_baseline_nicht_belegt")

    sl = payload.get("slos") or {}
    for key, code in (
        ("gateway_availability_slo_verified", "slo_gateway_fehlt"),
        ("system_health_p95_slo_verified", "slo_system_health_p95_fehlt"),
        ("data_freshness_slo_verified", "slo_data_freshness_fehlt"),
        ("live_safety_exposure_slo_verified", "slo_live_safety_fehlt"),
    ):
        if sl.get(key) is not True:
            failures.append(code)

    op = payload.get("operations") or {}
    if op.get("on_call_path_documented") is not True:
        failures.append("on_call_nicht_dokumentiert")
    if op.get("runbook_links_peer_reviewed") is not True:
        failures.append("runbook_peer_review_fehlt")
    if _missing_or_template(op.get("incident_response_drill_reference")):
        failures.append("incident_drill_ref_fehlt")

    saf = payload.get("safety") or {}
    if saf.get("no_metrics_secrets_in_repo") is not True:
        failures.append("metrics_secret_policy_verletzt")
    if saf.get("owner_signoff") is not True:
        failures.append("owner_signoff_fehlt")

    failures.extend(_secret_scan(payload))
    return {
        "status": "PASS" if not failures else "FAIL",
        "external_required": bool(failures),
        "failures": list(dict.fromkeys(failures)),
    }


def build_report_payload(
    *,
    alert_evidence_json: Path = DEFAULT_ALERT_EVIDENCE,
    observability_evidence_json: Path = DEFAULT_OBSERVABILITY_EVIDENCE,
) -> dict[str, Any]:
    var_mod = _load_verify_alert_routing_mod()
    doc_surface = analyze_observability_doc_surface()
    env = {k: v for k, v in os.environ.items()}

    alert_yaml_status: str = "SKIPPED"
    alert_yaml_issues: list[str] = []
    am_meta: dict[str, Any] = {}
    if ALERTMANAGER_EXAMPLE.is_file() and PROMETHEUS_ALERTS.is_file():
        alert_yaml_status, alert_yaml_issues, am_meta = var_mod.verify(
            ALERTMANAGER_EXAMPLE,
            True,
            env,
            PROMETHEUS_ALERTS,
        )
    else:
        if not ALERTMANAGER_EXAMPLE.is_file():
            alert_yaml_issues.append(f"fehlt: {ALERTMANAGER_EXAMPLE}")
        if not PROMETHEUS_ALERTS.is_file():
            alert_yaml_issues.append(f"fehlt: {PROMETHEUS_ALERTS}")

    alert_json = json.loads(alert_evidence_json.read_text(encoding="utf-8"))
    d1_status, d1_blockers, d1_warnings = var_mod.assess_delivery_evidence(alert_json)
    d1_secrets = var_mod.secret_surface_issues(alert_json)
    d1_ok = d1_status == "PASS" and not d1_secrets

    obs_json = json.loads(observability_evidence_json.read_text(encoding="utf-8"))
    obs_assessment = assess_observability_ops_evidence(obs_json)

    internal_issues: list[str] = []
    if not doc_surface.get("ok"):
        internal_issues.append("observability_docs_missing")
    if alert_yaml_status not in ("PASS",):
        internal_issues.append("alertmanager_prometheus_config_not_pass")
    if d1_secrets:
        internal_issues.append("alert_drill_json_secret_surface")

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "observability_doc_surface": doc_surface,
        "alertmanager_verify": {
            "status": alert_yaml_status,
            "issues": alert_yaml_issues,
            "meta": am_meta,
        },
        "alert_delivery_evidence": {
            "assessment_status": d1_status,
            "blockers": d1_blockers,
            "warnings": d1_warnings,
            "secret_surface": d1_secrets,
            "ok_strict": d1_ok,
        },
        "observability_ops_evidence": obs_assessment,
        "internal_issues": internal_issues,
        "external_required": [
            "Staging-/Shadow-Alert-Drill mit Zustellnachweis: siehe alert_routing_evidence.template.json und verify_alert_routing --evidence-json.",
            "Grafana/SLI-Baseline und SLO-Betriebsreview: siehe observability_slos_evidence.template.json.",
            "Owner-Signoff fuer On-Call-Pfad und Incident-Response vor privatem Live-Go.",
        ],
        "recommended_commands": [
            "python tools/verify_alert_routing.py --strict",
            "python tools/verify_alert_routing.py --evidence-json docs/production_10_10/alert_routing_evidence.template.json --strict",
            "pytest tests/unit/monitor_engine -q",
        ],
        "notes": [
            "Dieser Report fasst repo-lokale Pruefungen zusammen; kein Ersatz fuer echte Staging-Metrik-Baselines.",
            "private_live_allowed bleibt NO_GO bis verified externe Evidence und Matrix-Kategorien verified sind.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Observability and Alert-Routing Evidence Report",
        "",
        "## Zusammenfassung",
        "",
        f"- Erzeugt: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Doku vollstaendig: `{payload['observability_doc_surface']['ok']}`",
        f"- Alertmanager/Prometheus-Check: `{payload['alertmanager_verify']['status']}`",
        f"- Alert-Drill-JSON (strict): `{payload['alert_delivery_evidence']['ok_strict']}`",
        f"- Ops/SLO-JSON: `{payload['observability_ops_evidence']['status']}`",
        f"- Interne Issues: `{len(payload['internal_issues'])}`",
        "",
        "## Alertmanager / Prometheus (repo)",
        "",
    ]
    for item in payload["alertmanager_verify"]["issues"] or ["- Keine Befunde."]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Alert-Zustellung (evidence json)",
            "",
            f"- assess_delivery_evidence: `{payload['alert_delivery_evidence']['assessment_status']}`",
            f"- Warnings: {payload['alert_delivery_evidence']['warnings']}",
            "",
            "## Observability-Ops-Template",
            "",
            f"- Status: `{payload['observability_ops_evidence']['status']}`",
        ]
    )
    for f in payload["observability_ops_evidence"].get("failures") or []:
        lines.append(f"- `{f}`")
    lines.extend(["", "## Interne Issues", ""])
    lines.extend(f"- `{x}`" for x in (payload["internal_issues"] or ["-"]))
    lines.extend(["", "## Erforderlich extern", ""])
    lines.extend(f"- {x}" for x in payload["external_required"])
    lines.extend(["", "## Empfohlene Kommandos", ""])
    lines.extend(f"- `{x}`" for x in payload["recommended_commands"])
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {x}" for x in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert-evidence-json", type=Path, default=DEFAULT_ALERT_EVIDENCE)
    parser.add_argument("--observability-evidence-json", type=Path, default=DEFAULT_OBSERVABILITY_EVIDENCE)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--write-observability-template",
        type=Path,
        help="Schreibt Standard-Observability-Evidence-Template und beendet (optionaler Pfad).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 bei internen Issues (Doku, Alertmanager-Verify, Secret-Surface in Alert-JSON).",
    )
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Zusaetzlich: alert delivery + observability_ops Evidence muessen PASS (nur mit verified JSONs).",
    )
    args = parser.parse_args(argv)

    if args.write_observability_template:
        path = args.write_observability_template
        if path.is_dir():
            path = path / "observability_slos_evidence.template.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(build_observability_ops_template(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"observability_alert_evidence_report: wrote {path}")
        return 0

    payload = build_report_payload(
        alert_evidence_json=args.alert_evidence_json,
        observability_evidence_json=args.observability_evidence_json,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")

    print(
        "observability_alert_evidence_report: "
        f"internal={len(payload['internal_issues'])} "
        f"am={payload['alertmanager_verify']['status']} "
        f"ad={payload['alert_delivery_evidence']['assessment_status']} "
        f"ops={payload['observability_ops_evidence']['status']}"
    )
    if args.strict and payload["internal_issues"]:
        return 1
    if args.strict_external:
        if not payload["alert_delivery_evidence"]["ok_strict"]:
            return 1
        if payload["observability_ops_evidence"]["status"] != "PASS":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
