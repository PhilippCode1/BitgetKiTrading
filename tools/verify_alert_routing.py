#!/usr/bin/env python3
# ruff: noqa: E501
"""Validiert Alertmanager-Beispielkonfiguration: Routen, Receiver, Platzhalter, P0-Abdeckung."""
from __future__ import annotations

import argparse
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
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur parsen, Exit 0 bei lesbarer YAML (kein Inhaltscheck).",
    )
    args = ap.parse_args()

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
