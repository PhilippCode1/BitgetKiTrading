#!/usr/bin/env python3
"""Kombinierter Evidence-Report: Deployment-Paritaet (Doku, ENV, Compose, Release-Sanity) und Supply-Chain-Nachweise."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEPLOY_EVIDENCE = ROOT / "docs" / "production_10_10" / "deployment_staging_parity_evidence.template.json"
DEFAULT_SUPPLY_EVIDENCE = ROOT / "docs" / "production_10_10" / "supply_chain_release_audit_evidence.template.json"
SCHEMA_V = 1

REQUIRED_DOCS: tuple[Path, ...] = (
    ROOT / "docs" / "Deploy.md",
    ROOT / "docs" / "compose_runtime.md",
    ROOT / "docs" / "ci_release_gates.md",
    ROOT / "STAGING_PARITY.md",
    ROOT / "docs" / "REPO_SBOM_AND_RELEASE_METADATA.md",
)


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _missing_template(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and (v.strip() == "" or v.startswith("CHANGE_ME")):
        return True
    return False


def analyze_doc_surface() -> dict[str, Any]:
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED_DOCS if not p.is_file()]
    return {"ok": not missing, "missing": missing}


def _run(cmd: list[str], *, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        tail = (r.stdout or "")[-2000:] + (r.stderr or "")[-2000:]
        return r.returncode, tail
    except FileNotFoundError as e:
        return 127, str(e)
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def run_validate_env_examples() -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    specs: tuple[tuple[str, str, list[str]], ...] = (
        (".env.local.example", "local", []),
        (".env.shadow.example", "shadow", ["--template"]),
        (".env.production.example", "production", ["--template"]),
    )
    all_ok = True
    for env_file, profile, extra in specs:
        path = ROOT / env_file
        if not path.is_file():
            runs.append(
                {
                    "env_file": env_file,
                    "profile": profile,
                    "ok": False,
                    "exit_code": -1,
                    "note": "file_missing",
                }
            )
            all_ok = False
            continue
        cmd = [
            sys.executable,
            str(ROOT / "tools" / "validate_env_profile.py"),
            "--env-file",
            str(path),
            "--profile",
            profile,
            *extra,
        ]
        code, _tail = _run(cmd, timeout=90)
        ok = code == 0
        all_ok = all_ok and ok
        runs.append({"env_file": env_file, "profile": profile, "ok": ok, "exit_code": code})
    return {"ok": all_ok, "runs": runs}


def run_docker_compose_config() -> dict[str, Any]:
    compose = ROOT / "docker-compose.yml"
    if not compose.is_file():
        return {"ok": False, "exit_code": -1, "note": "docker-compose.yml fehlt"}
    code, tail = _run(
        ["docker", "compose", "-f", str(compose), "config", "--quiet"],
        timeout=60,
    )
    return {
        "ok": code == 0,
        "exit_code": code,
        "stderr_tail": tail[-500:] if code != 0 else "",
    }


def run_release_sanity() -> dict[str, Any]:
    code, _ = _run([sys.executable, str(ROOT / "tools" / "release_sanity_checks.py")], timeout=120)
    return {"ok": code == 0, "exit_code": code}


def run_pip_audit_gate() -> dict[str, Any]:
    code, tail = _run([sys.executable, str(ROOT / "tools" / "pip_audit_supply_chain_gate.py")], timeout=180)
    return {"ok": code == 0, "exit_code": code, "tail": tail[-800:] if code != 0 else ""}


def assess_deployment_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != SCHEMA_V:
        failures.append("schema")
    if payload.get("status") != "verified":
        failures.append("status")
    for k in ("reviewed_by", "reviewed_at", "environment", "git_sha"):
        if _missing_template(payload.get(k)):
            failures.append(k)
    ch = payload.get("checks") or {}
    for key, code in (
        ("staging_or_shadow_smoke_pass", "smoke"),
        ("api_integration_smoke_or_equivalent", "api_smoke"),
        ("disallow_loopback_gateway_for_deploy_profile", "loopback"),
        ("compose_runtime_effective_env_reviewed", "compose_review"),
    ):
        if ch.get(key) is not True:
            failures.append(code)
    art = payload.get("artifacts") or {}
    for k in ("smoke_log_uri", "docker_compose_effective_excerpt_uri"):
        if _missing_template(art.get(k)):
            failures.append(k)
    saf = payload.get("safety") or {}
    if saf.get("no_secrets_in_logs") is not True:
        failures.append("secrets_in_logs")
    if saf.get("owner_signoff") is not True:
        failures.append("owner_signoff")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def assess_supply_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != SCHEMA_V:
        failures.append("schema")
    if payload.get("status") != "verified":
        failures.append("status")
    for k in ("reviewed_by", "reviewed_at", "git_sha"):
        if _missing_template(payload.get(k)):
            failures.append(k)
    ci = payload.get("ci") or {}
    if ci.get("last_pip_audit_gate_pass") is not True:
        failures.append("pip_audit_gate")
    if ci.get("last_pnpm_audit_high_gate_pass") is not True:
        failures.append("pnpm_audit_gate")
    if _missing_template(ci.get("ci_run_uri")):
        failures.append("ci_run_uri")
    fin = payload.get("findings") or {}
    open_v = fin.get("open_high_or_critical_supplier_issues")
    if open_v is None or (isinstance(open_v, int) and open_v > 0):
        if open_v is None:
            failures.append("supplier_issues_unknown")
        elif isinstance(open_v, int) and open_v > 0:
            failures.append("supplier_issues_open")
    if _missing_template(fin.get("last_sbom_or_export_uri")):
        failures.append("sbom_uri")
    saf = payload.get("safety") or {}
    if saf.get("no_tokens_in_report_exports") is not True:
        failures.append("tokens_in_export")
    if saf.get("owner_signoff") is not True:
        failures.append("owner_signoff")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def build_report_payload(
    *,
    deployment_json: Path = DEFAULT_DEPLOY_EVIDENCE,
    supply_json: Path = DEFAULT_SUPPLY_EVIDENCE,
    run_pip_audit: bool = False,
) -> dict[str, Any]:
    docs = analyze_doc_surface()
    env_runs = run_validate_env_examples()
    docker = run_docker_compose_config()
    release = run_release_sanity()
    pip_result: dict[str, Any] | None = None
    if run_pip_audit:
        pip_result = run_pip_audit_gate()

    dep_a = assess_deployment_evidence(json.loads(deployment_json.read_text(encoding="utf-8")))
    sup_a = assess_supply_evidence(json.loads(supply_json.read_text(encoding="utf-8")))

    internal: list[str] = []
    if not docs["ok"]:
        internal.append("required_docs_missing")
    if not env_runs["ok"]:
        internal.append("validate_env_example_failed")
    if not docker["ok"]:
        internal.append("docker_compose_config_failed")
    if not release["ok"]:
        internal.append("release_sanity_checks_failed")
    if run_pip_audit and pip_result and not pip_result.get("ok"):
        internal.append("pip_audit_supply_chain_gate_failed")

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "doc_surface": docs,
        "validate_env_examples": env_runs,
        "docker_compose_config": docker,
        "release_sanity_checks": release,
        "pip_audit_supply_chain": pip_result,
        "deployment_evidence_assessment": dep_a,
        "supply_chain_evidence_assessment": sup_a,
        "internal_issues": internal,
        "external_required": [
            "Echter Staging-/Shadow-Smoke mit Logs und ohne Secrets (deployment_staging_parity_evidence).",
            "CI-Nachweis zu pip-/pnpm-Audit und SBOM-Export (supply_chain_release_audit_evidence).",
        ],
        "recommended_commands": [
            "python tools/validate_env_profile.py --env-file .env.local.example --profile local",
            "python tools/validate_env_profile.py --env-file .env.shadow.example --profile shadow --template",
            "python tools/validate_env_profile.py --env-file .env.production.example --profile production --template",
            "docker compose config --quiet",
            "python tools/release_sanity_checks.py",
            "python tools/pip_audit_supply_chain_gate.py",
        ],
        "notes": [
            "Standardlauf prueft Repo-Artefakte; pip-audit nutzt Netzwerk (OSV) — optional mit --with-pip-audit.",
        ],
    }


def render_markdown(p: dict[str, Any]) -> str:
    lines = [
        "# Deployment und Supply-Chain Evidence Report",
        "",
        f"- Erzeugt: `{p['generated_at']}` · SHA `{p['git_sha']}`",
        f"- Doku vollstaendig: `{p['doc_surface']['ok']}`",
        f"- validate_env (Beispieldateien): `{p['validate_env_examples']['ok']}`",
        f"- docker compose config: `{p['docker_compose_config']['ok']}`",
        f"- release_sanity_checks: `{p['release_sanity_checks']['ok']}`",
    ]
    if p.get("pip_audit_supply_chain"):
        pa = p["pip_audit_supply_chain"]
        lines.append(f"- pip_audit_gate (optional): ok=`{pa.get('ok')}` code=`{pa.get('exit_code')}`")
    lines.extend(
        [
            f"- extern Deployment-Template: `{p['deployment_evidence_assessment']['status']}`",
            f"- extern Supply-Template: `{p['supply_chain_evidence_assessment']['status']}`",
            f"- interne Blocker: {len(p['internal_issues'])}",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment-json", type=Path, default=DEFAULT_DEPLOY_EVIDENCE)
    parser.add_argument("--supply-json", type=Path, default=DEFAULT_SUPPLY_EVIDENCE)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--with-pip-audit",
        action="store_true",
        help="Fuehrt pip_audit_supply_chain_gate aus (Netzwerk); bei Fehler interner Blocker.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 bei internen issues (Doku, ENV, Compose, release_sanity; optional pip).",
    )
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Zusaetzlich: beide externen JSON-Assessments muessen PASS sein.",
    )
    args = parser.parse_args(argv)

    payload = build_report_payload(
        deployment_json=args.deployment_json,
        supply_json=args.supply_json,
        run_pip_audit=args.with_pip_audit,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "deployment_supply_chain_evidence_report: internal="
        f"{len(payload['internal_issues'])} dep_ext={payload['deployment_evidence_assessment']['status']} "
        f"sup_ext={payload['supply_chain_evidence_assessment']['status']}"
    )
    if args.strict and payload["internal_issues"]:
        return 1
    if args.strict_external:
        if payload["deployment_evidence_assessment"]["status"] != "PASS":
            return 1
        if payload["supply_chain_evidence_assessment"]["status"] != "PASS":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())