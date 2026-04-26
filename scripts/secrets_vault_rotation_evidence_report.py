#!/usr/bin/env python3
"""Erzeugt Evidence fuer ENV-, Secrets-, Vault- und Rotation-Safety."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from functools import lru_cache
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scripts.secrets_rotation_drill import build_simulated_drill  # noqa: E402
from shared_py.secret_lifecycle import (  # noqa: E402
    all_secret_policies,
    build_secret_rotation_audit_payload,
    secret_reuse_across_env_is_forbidden,
)
from tools.inventory_secret_surfaces import scan_repo  # noqa: E402
from tools.validate_env_profile import (  # noqa: E402
    bootstrap_issues,
    conditional_env_issues,
    llm_gateway_base_issues,
    load_dotenv,
    next_public_secret_key_issues,
)

ENV_TEMPLATES = (
    (".env.local.example", "local"),
    (".env.shadow.example", "shadow"),
    (".env.production.example", "production"),
)
REQUIRED_CRITICAL_POLICIES = (
    "BITGET_API_KEY",
    "BITGET_API_SECRET",
    "BITGET_API_PASSPHRASE",
    "GATEWAY_JWT_SECRET",
    "INTERNAL_API_KEY",
    "JWT_SECRET",
    "ENCRYPTION_KEY",
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
    "VAULT_TOKEN",
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


def _template_assessment(path_name: str, profile: str) -> dict[str, Any]:
    path = ROOT / path_name
    if not path.is_file():
        return {"path": path_name, "profile": profile, "ok": False, "issues": ["env_template_missing"]}
    env = load_dotenv(path)
    issues: list[str] = []
    issues.extend(conditional_env_issues(env, profile, template=True))
    issues.extend(next_public_secret_key_issues(env))
    issues.extend(llm_gateway_base_issues(env, profile))
    issues.extend(bootstrap_issues(env, profile, template=True))
    return {
        "path": path_name,
        "profile": profile,
        "ok": not issues,
        "issues": issues,
        "next_public_secret_issues": next_public_secret_key_issues(env),
        "live_trade_enable": env.get("LIVE_TRADE_ENABLE"),
        "live_broker_enabled": env.get("LIVE_BROKER_ENABLED"),
        "llm_fake_provider": env.get("LLM_USE_FAKE_PROVIDER"),
    }


@lru_cache(maxsize=1)
def _surface_assessment() -> dict[str, Any]:
    payload = scan_repo()
    findings = payload["findings"]
    browser_leaks = [item for item in findings if item["rule"] == "next_public_secret_name"]
    server_secret_rows = [
        item for item in findings if item["rule"] in {"jwt_secret_assignment", "internal_api_key_assignment", "secret_key_assignment"}
    ]
    return {
        "row_count": payload["scanned_files"],
        "server_secret_count": len(server_secret_rows),
        "browser_public_leak_count": len(browser_leaks),
        "browser_public_leaks": browser_leaks,
        "env_files_not_ignored": payload["env_files_not_ignored"],
    }


def _rotation_policy_assessment(now: datetime) -> dict[str, Any]:
    policies = {policy.id: policy for policy in all_secret_policies()}
    missing = [name for name in REQUIRED_CRITICAL_POLICIES if name not in policies]
    stale_examples = [
        build_secret_rotation_audit_payload(
            name,
            environment="production",
            reason="synthetic_rotation_expiry_check",
            last_rotated_at=now - timedelta(days=400),
            as_of=now,
        )
        for name in ("BITGET_API_SECRET", "GATEWAY_JWT_SECRET", "DATABASE_URL")
    ]
    reuse_forbidden = sorted(
        name for name in REQUIRED_CRITICAL_POLICIES if secret_reuse_across_env_is_forbidden(name)
    )
    return {
        "policy_count": len(policies),
        "required_policy_missing": missing,
        "reuse_forbidden_critical": reuse_forbidden,
        "stale_examples": stale_examples,
    }


def build_report_payload() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    templates = [_template_assessment(path, profile) for path, profile in ENV_TEMPLATES]
    surface = _surface_assessment()
    rotation = _rotation_policy_assessment(now)
    drill = build_simulated_drill(as_of=now)
    external_required = [
        "vault_runtime_secret_store_attestation_missing",
        "real_secret_rotation_drill_missing",
        "owner_signed_secret_rotation_acceptance_missing",
    ]
    failures: list[str] = []
    failures.extend(f"template_failed:{item['path']}" for item in templates if not item["ok"])
    if surface["browser_public_leak_count"] > 0:
        failures.append("browser_public_secret_leak_detected")
    if rotation["required_policy_missing"]:
        failures.append("critical_secret_policy_missing")
    if drill.get("raw_secret_values_included") is not False:
        failures.append("rotation_drill_contains_raw_secret_values")
    return {
        "generated_at": now.isoformat(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "templates": templates,
        "secret_surface": surface,
        "rotation_policy": rotation,
        "simulated_rotation_drill": {
            "mode": drill["mode"],
            "raw_secret_values_included": drill["raw_secret_values_included"],
            "inventory_count": drill["inventory_count"],
            "go_no_go": drill["go_no_go"],
        },
        "external_required": external_required,
        "failures": failures,
        "notes": [
            "Repo-lokale Evidence ohne echte Secrets und ohne echte Vault-Zugriffe.",
            "Production-Templates duerfen Platzhalter enthalten, aber keine unsicheren Live-Defaults oder NEXT_PUBLIC-Secret-Namen.",
            "Private Live bleibt blockiert, bis echter Secret-Store, Rotation-Drill und Owner-Signoff extern belegt sind.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Secrets / Vault / Rotation Evidence Report",
        "",
        "Status: repo-lokaler Nachweis fuer ENV-Templates, Secret-Surfaces und Rotation-Policies ohne echte Secrets.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private Live: `{payload['private_live_decision']}`",
        f"- Full Autonomous Live: `{payload['full_autonomous_live']}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- External Required: `{len(payload['external_required'])}`",
        f"- Browser-Public-Secret-Leaks: `{payload['secret_surface']['browser_public_leak_count']}`",
        f"- Secret-Surface-Zeilen: `{payload['secret_surface']['row_count']}`",
        f"- Rotation-Policies: `{payload['rotation_policy']['policy_count']}`",
        "",
        "## ENV-Templates",
        "",
        "| Datei | Profil | OK | Issues |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload["templates"]:
        issues = ", ".join(f"`{issue}`" for issue in item["issues"]) or "-"
        lines.append(f"| `{item['path']}` | `{item['profile']}` | `{item['ok']}` | {issues} |")
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
        "secrets_vault_rotation_evidence_report: "
        f"templates={len(payload['templates'])} "
        f"failures={len(payload['failures'])} "
        f"external_required={len(payload['external_required'])}"
    )
    if args.strict and payload["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
