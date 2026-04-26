#!/usr/bin/env python3
# ruff: noqa: E501
"""Validiert Alertmanager-Beispielkonfiguration: Routen, Receiver, Platzhalter, P0-Abdeckung."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise SystemExit("PyYAML fehlt: pip install PyYAML (requirements-dev.txt)") from e

_REPO = Path(__file__).resolve().parents[1]
ALERT_EVIDENCE_SCHEMA_VERSION = "alert-routing-evidence-v1"
DEFAULT_EVIDENCE_TEMPLATE = _REPO / "docs" / "production_10_10" / "alert_routing_evidence.template.json"
SECRET_LIKE_KEYS = ("webhook", "url", "token", "secret", "password", "api_key", "authorization", "routing_key")


def build_evidence_template() -> dict[str, Any]:
    return {
        "schema_version": ALERT_EVIDENCE_SCHEMA_VERSION,
        "environment": "staging",
        "drill_started_at": "",
        "drill_completed_at": "",
        "git_sha": "",
        "operator": "",
        "evidence_reference": "",
        "test_alert_label": "test_alert=true",
        "p0_route_verified": False,
        "p1_route_verified": False,
        "kill_switch_alert_delivered": False,
        "reconcile_alert_delivered": False,
        "market_data_stale_alert_delivered": False,
        "gateway_auth_alert_delivered": False,
        "delivery_channel": "",
        "delivery_proof_reference": "",
        "acknowledged_by_human": False,
        "ack_latency_seconds": None,
        "ack_latency_budget_seconds": 900,
        "dedupe_verified": False,
        "runbook_link_verified": False,
        "main_console_alert_state_verified": False,
        "no_secret_in_alert_payload": False,
        "owner_signoff": False,
        "webhook_url": "[REDACTED]",
        "routing_key": "[REDACTED]",
        "authorization": "[REDACTED]",
        "notes_de": "Template: echten Staging-Alert-Drill extern ausfuehren; Secrets niemals im Repo speichern.",
    }


def secret_surface_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        # Boolean-Compliance-Flag; kein Geheimnis (Schluessel enthaelt 'secret' als Wort).
        if lowered == "no_secret_in_alert_payload":
            continue
        if any(fragment in lowered for fragment in SECRET_LIKE_KEYS):
            if value not in (None, "", "[REDACTED]", "REDACTED", "not_stored_in_repo"):
                issues.append(f"secret_like_field_not_redacted:{key}")
    return issues


def _non_negative_number(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def assess_delivery_evidence(payload: dict[str, Any] | None) -> tuple[str, list[str], list[str]]:
    if not payload:
        return "FAIL", ["alert_delivery_evidence_missing"], []
    blockers: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != ALERT_EVIDENCE_SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if payload.get("environment") not in {"staging", "shadow", "production_shadow"}:
        blockers.append("environment_invalid")
    for key, code in (
        ("drill_started_at", "drill_started_at_missing"),
        ("drill_completed_at", "drill_completed_at_missing"),
        ("git_sha", "git_sha_missing"),
        ("operator", "operator_missing"),
        ("evidence_reference", "evidence_reference_missing"),
        ("test_alert_label", "test_alert_label_missing"),
        ("delivery_channel", "delivery_channel_missing"),
        ("delivery_proof_reference", "delivery_proof_reference_missing"),
    ):
        if not str(payload.get(key) or "").strip():
            blockers.append(code)
    required_true = (
        ("p0_route_verified", "p0_route_not_verified"),
        ("p1_route_verified", "p1_route_not_verified"),
        ("kill_switch_alert_delivered", "kill_switch_alert_not_delivered"),
        ("reconcile_alert_delivered", "reconcile_alert_not_delivered"),
        ("market_data_stale_alert_delivered", "market_data_stale_alert_not_delivered"),
        ("gateway_auth_alert_delivered", "gateway_auth_alert_not_delivered"),
        ("acknowledged_by_human", "human_ack_missing"),
        ("dedupe_verified", "dedupe_not_verified"),
        ("runbook_link_verified", "runbook_link_not_verified"),
        ("main_console_alert_state_verified", "main_console_alert_state_not_verified"),
        ("no_secret_in_alert_payload", "alert_payload_secret_safety_not_verified"),
    )
    for key, code in required_true:
        if payload.get(key) is not True:
            blockers.append(code)
    latency = _non_negative_number(payload, "ack_latency_seconds")
    budget = _non_negative_number(payload, "ack_latency_budget_seconds")
    if latency is None:
        blockers.append("ack_latency_seconds_missing")
    if budget is None:
        blockers.append("ack_latency_budget_seconds_missing")
    if latency is not None and budget is not None and latency > budget:
        blockers.append("ack_latency_budget_exceeded")
    if payload.get("owner_signoff") is not True:
        warnings.append("owner_signoff_missing_external_required")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return status, blockers, warnings


def _render_evidence_md(payload: dict[str, Any], status: str, blockers: list[str], warnings: list[str], secret_issues: list[str]) -> str:
    lines = [
        "# Alert Routing Delivery Evidence Check",
        "",
        "Status: prueft externen Alert-Zustellnachweis ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Environment: `{payload.get('environment')}`",
        f"- Git SHA: `{payload.get('git_sha') or 'missing'}`",
        f"- Operator: `{payload.get('operator') or 'missing'}`",
        f"- Kanal: `{payload.get('delivery_channel') or 'missing'}`",
        f"- Ack-Latenz Sekunden: `{payload.get('ack_latency_seconds')}` / Budget `{payload.get('ack_latency_budget_seconds')}`",
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
            "- YAML-Strukturtests ersetzen keinen echten Zustellnachweis.",
            "- Live bleibt `NO_GO`, bis P0/P1-Routen, menschliche Quittierung, Runbook-Link, Main-Console-State und Owner-Signoff extern belegt sind.",
            "",
        ]
    )
    return "\n".join(lines)


# Mindest-Abdeckung: Teilstrings in Route-Matchern (siehe prometheus-alerts.yml)
def _check_route_coverage(route_blob: str) -> list[str]:
    b = route_blob.lower()
    need: list[tuple[str, list[str]]] = [
        ("P0/Trading-Blocker", ["alert_tier", "safetylatch"]),
        ("Reconcile", ["reconcile"]),
        ("Kill-Switch", ["killswitch"]),
        ("Stale market data", ["marketpipeline", "datastale"]),
        ("Gateway auth", ["gatewayauth"]),
        ("DB/Redis/Infra-Proxy", ["redisstream", "redisdown", "databasedown"]),
        ("LLM error/latency", ["llmhigh"]),
    ]
    out: list[str] = []
    for label, alts in need:
        if not any(a in b for a in alts):
            out.append(
                f"Route-Matcher fehlt (Kategorie: {label}, erwartet z.B. {alts[0]})"
            )
    return out


def _read_env_file(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in out:
            out[k] = v
    return out


def _dump_routes_for_search(data: Any) -> str:
    if isinstance(data, dict):
        return " ".join(f"{k}={_dump_routes_for_search(v)}" for k, v in data.items())
    if isinstance(data, list):
        return " ".join(_dump_routes_for_search(x) for x in data)
    return str(data)


def _find_env_refs(text: str) -> set[str]:
    return set(re.findall(r"\$\{([A-Z0-9_]+)(?::-[^}]*)?\}", text))


def _receiver_by_name(recs: list[Any], name: str) -> dict[str, Any] | None:
    for r in recs:
        if isinstance(r, dict) and r.get("name") == name:
            return r
    return None


def _receiver_has_channel(rec: dict[str, Any]) -> bool:
    keys = (
        "slack_configs",
        "pagerduty_configs",
        "webhook_configs",
        "email_configs",
        "opsgenie_configs",
        "discord_configs",
        "telegram_configs",
        "msteams_configs",
    )
    for k in keys:
        block = rec.get(k)
        if not block:
            continue
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            for urlkey in (
                "api_url",
                "url",
                "api_url_file",
                "routing_key",
                "service_key",
                "to",
            ):
                val = item.get(urlkey)
                if val is not None and str(val).strip() != "":
                    return True
    return False


def _count_routes(r: Any) -> int:
    if not isinstance(r, dict):
        return 0
    n = 0
    for sub in r.get("routes") or []:
        n += 1 + _count_routes(sub)
    return n


def _collect_rule_meta(alerts_path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not alerts_path.is_file():
        return {}, [f"Prometheus-Alertdatei fehlt: {alerts_path}"]
    raw = alerts_path.read_text(encoding="utf-8", errors="replace")
    data = yaml.safe_load(raw) or {}
    groups = data.get("groups")
    if not isinstance(groups, list):
        return {}, [f"`groups` fehlt/ungültig in {alerts_path}"]
    out: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        for rule in g.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            name = str(rule.get("alert") or "").strip()
            if not name:
                continue
            labels = rule.get("labels") if isinstance(rule.get("labels"), dict) else {}
            ann = (
                rule.get("annotations")
                if isinstance(rule.get("annotations"), dict)
                else {}
            )
            out[name] = {
                "severity": str(labels.get("severity") or "").strip().lower(),
                "alert_tier": str(labels.get("alert_tier") or "").strip().lower(),
                "runbook": str(ann.get("runbook") or "").strip(),
            }
            if not out[name]["runbook"]:
                issues.append(f"Alert `{name}` ohne annotations.runbook")
    return out, issues


def verify(
    path: Path,
    strict: bool,
    env: dict[str, str],
    alerts_path: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        return "FAIL", ["YAML-Root kein Mapping"], _meta({}, path, 0, env)

    top_route = data.get("route")
    if not isinstance(top_route, dict):
        return "FAIL", ["kein `route:` Block"], _meta(data, path, 0, env)
    if not (top_route.get("receiver") or "").strip():
        return "FAIL", ["route.receiver fehlt"], _meta(data, path, 0, env)

    recs = data.get("receivers")
    if not isinstance(recs, list) or len(recs) == 0:
        return "FAIL", ["`receivers` leer oder fehlt"], _meta(data, path, 0, env)

    names = {r.get("name") for r in recs if isinstance(r, dict)}
    if None in names or "" in names:
        return "FAIL", ["Receiver ohne `name`"], _meta(data, path, 0, env)

    issues: list[str] = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        nm = str(r.get("name", ""))
        if not _receiver_has_channel(r):
            issues.append(
                f"Receiver `{nm}` ohne Ziel (slack/webhook/pagerduty/email/…)"
            )

    route_blob = _dump_routes_for_search(data.get("route")).lower()
    issues.extend(_check_route_coverage(route_blob))

    if top_route.get("group_by") is None:
        issues.append("route.group_by fehlt (Deduplication/Gruppierung)")

    rule_meta, rule_issues = _collect_rule_meta(alerts_path)
    issues.extend(rule_issues)

    # Kritische Mindest-Alerts müssen in Rule-File existieren und als critical/p0 markiert sein.
    required_critical = [
        "GatewayHighErrorRate",
        "LiveBrokerDown",
        "KillSwitchActive",
        "MarketPipelineLag",
        "ReconcileLagHigh",
    ]
    for rn in required_critical:
        m = rule_meta.get(rn)
        if m is None:
            issues.append(f"Kritischer Alert `{rn}` fehlt in {alerts_path.name}")
            continue
        sev = str(m.get("severity") or "")
        tier = str(m.get("alert_tier") or "")
        if sev != "critical" and tier != "p0":
            issues.append(
                f"Kritischer Alert `{rn}` ist weder severity=critical noch alert_tier=p0 "
                f"(aktuell severity={sev!r}, tier={tier!r})"
            )

    # Für LLM/Gateway-Auth erwarten wir mindestens warning+ mit Runbook.
    for rn in ("LlmHighErrorRate", "GatewayAuthAnomalies"):
        m = rule_meta.get(rn)
        if m is None:
            issues.append(f"Alert `{rn}` fehlt in {alerts_path.name}")
            continue
        sev = str(m.get("severity") or "")
        if sev not in ("warning", "critical"):
            issues.append(f"Alert `{rn}` ohne severity warning/critical")

    refs = _find_env_refs(raw)
    p0_rec = _receiver_by_name(recs, "p0_trading_halt")
    if strict and p0_rec:
        if not p0_rec.get("pagerduty_configs"):
            issues.append(
                "strict: Receiver `p0_trading_halt` ohne pagerduty_configs "
                "(P0 braucht On-Call, nicht nur Slack)"
            )
        if not p0_rec.get("slack_configs"):
            issues.append("strict: p0_trading_halt ohne slack_configs")

    if issues:
        return "FAIL", issues, _meta(data, path, len(refs), env, alerts_path)
    return "PASS", [], _meta(data, path, len(refs), env, alerts_path)


def _meta(
    data: dict[str, Any],
    path: Path,
    env_ref_count: int,
    env: dict[str, str] | None = None,
    alerts_path: Path | None = None,
) -> dict[str, Any]:
    r = data.get("route")
    nsub = 0
    if isinstance(r, dict):
        nsub = _count_routes(r)
    u = 0
    if env is not None:
        raw = path.read_text(encoding="utf-8", errors="replace")
        for v in _find_env_refs(raw):
            if v.startswith("ALERTMANAGER_") and not str(env.get(v, "")).strip():
                u += 1
    return {
        "config": str(path),
        "alerts_file": str(alerts_path) if alerts_path else "",
        "receivers_count": len(data.get("receivers") or ()),
        "subroutes_count": nsub,
        "env_var_refs": env_ref_count,
        "unresolved_alertmanager_env": u,
    }


def _render_md(
    status: str,
    issues: list[str],
    meta: dict[str, Any],
) -> str:
    uenv = meta.get("unresolved_alertmanager_env", 0)
    lines = [
        "# Alert-Routing-Verifikation",
        "",
        f"**Status:** `{status}`",
        f"**Config:** `{meta.get('config', '')}`",
        f"**Receiver:** {meta.get('receivers_count', 0)} | **Unterrouten (geschätzt):** {meta.get('subroutes_count', 0)}",
        f"**${{ENV}}-Platzhalter in Datei:** {meta.get('env_var_refs', 0)} | "
        f"**unaufgelöst (ALERTMANAGER_*):** {uenv}",
        "",
    ]
    if issues:
        lines.append("## Befunde")
        for i in issues:
            lines.append(f"- {i}")
        lines.append("")
    else:
        lines.append("## Befunde\n\nKeine harten Verstöße (Struktur).")
        lines.append("")
    lines.append(
        "*Echter On-Call-Drill (Slack/Pager reicht) = extern; siehe* "
        "`docs/production_10_10/05_alert_routing_and_incident_drill.md` *.*\n"
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Alertmanager-Beispielkonfiguration pruefen."
    )
    ap.add_argument(
        "--config",
        type=Path,
        default=_REPO / "infra" / "observability" / "alertmanager.yml.example",
    )
    ap.add_argument(
        "--strict", action="store_true", help="ENV-Refs muessen aufgeloest sein"
    )
    ap.add_argument(
        "--alerts-file",
        type=Path,
        default=_REPO / "infra" / "observability" / "prometheus-alerts.yml",
        help="Prometheus-Alertregeln fuer Severity/Runbook-Pruefung",
    )
    ap.add_argument("--env-file", type=Path, default=None)
    ap.add_argument("--report-md", type=Path, default=None, dest="report")
    ap.add_argument("--evidence-json", type=Path, default=None)
    ap.add_argument("--write-template", type=Path, default=None)
    ap.add_argument("--output-json", type=Path, default=None)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur parsen, Exit 0 bei lesbarer YAML (kein Inhaltscheck).",
    )
    args = ap.parse_args()
    if args.write_template is not None:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_evidence_template(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote template: {args.write_template}")
        return 0
    if args.evidence_json is not None:
        loaded = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Evidence root muss ein JSON-Objekt sein.")
        status, blockers, warnings = assess_delivery_evidence(loaded)
        secret_issues = secret_surface_issues(loaded)
        payload = {
            "ok": status == "PASS" and not secret_issues,
            "status": status,
            "blockers": blockers + secret_issues,
            "warnings": warnings,
        }
        text = _render_evidence_md(loaded, status, blockers, warnings, secret_issues)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding="utf-8")
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        if not args.report:
            print(text)
        return 1 if args.strict and not payload["ok"] else 0

    env: dict[str, str] = {k: v for k, v in os.environ.items()}
    if args.env_file and args.env_file.is_file():
        env.update(_read_env_file(args.env_file))

    if not args.config.is_file():
        print(f"ERROR: Datei fehlt: {args.config}", file=sys.stderr)
        return 1

    if args.dry_run:
        raw = args.config.read_text(encoding="utf-8", errors="replace")
        yaml.safe_load(raw)
        print("OK: YAML parse", file=sys.stderr)
        return 0

    st, issues, meta = verify(args.config, args.strict, env, args.alerts_file)
    text = _render_md(st, issues, meta)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
        print(f"Written: {args.report}", file=sys.stderr)
    else:
        print(text)
    if st == "PASS":
        return 0
    if st == "NO_EVIDENCE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
