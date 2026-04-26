#!/usr/bin/env python3
"""
Evidence-Report: CI-Pflichtjobs (lokal), GitHub-Branch-Protection (optional), Template.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise SystemExit("PyYAML fehlt (requirements-dev.txt)") from e

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_github_branch_protection import (  # noqa: E402, I001
    DEFAULT_REPO as DEFAULT_GH_REPO,
    MANDATORY,
    run as github_branch_run,
)

_DEFAULT_EXT_NAME = "branch_protection_evidence.template.json"
DEFAULT_EXT = ROOT / "docs" / "production_10_10" / _DEFAULT_EXT_NAME
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_DOCS: tuple[Path, ...] = (
    ROOT / "docs" / "ci_release_gates.md",
    ROOT / "release-readiness.md",
)
SCHEMA_V = 1


def _now() -> str:
    z = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    return z.replace("+00:00", "Z")


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


def _missing_templ(v: Any) -> bool:
    if v is None:
        return True
    if not isinstance(v, str):
        return False
    bad = v.strip() == "" or "CHANGE_ME" in v or v.startswith("CHANGE_")
    if bad:
        return True
    return False


def analyze_ci_yml_mandatory_jobs() -> dict[str, Any]:
    if not CI_YML.is_file():
        return {
            "ok": False,
            "job_ids": [],
            "missing_mandatory": list(MANDATORY),
            "note": "ci.yml fehlt",
        }
    raw = CI_YML.read_text(encoding="utf-8", errors="replace")
    data = yaml.safe_load(raw) or {}
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return {"ok": False, "job_ids": [], "missing_mandatory": list(MANDATORY)}
    job_ids = [str(k) for k in jobs.keys()]
    missing = [j for j in MANDATORY if j not in job_ids]
    display_names: dict[str, str] = {}
    for job_id in MANDATORY:
        spec = jobs.get(job_id)
        if isinstance(spec, dict):
            name = spec.get("name")
            display_names[job_id] = str(name).strip() if isinstance(name, str) and name.strip() else job_id
        else:
            display_names[job_id] = job_id
    expected_checks = [f"ci / {display_names[job_id]}" for job_id in MANDATORY]
    return {
        "ok": len(missing) == 0,
        "job_ids": job_ids,
        "expected_required_checks": expected_checks,
        "missing_mandatory": missing,
    }


def analyze_doc_hints() -> dict[str, Any]:
    missing: list[str] = []
    weak: list[str] = []
    for p in REQUIRED_DOCS:
        if not p.is_file():
            missing.append(str(p.relative_to(ROOT)))
            continue
        text = p.read_text(encoding="utf-8", errors="replace").lower()
        if p.name == "ci_release_gates.md":
            if "branch" not in text or "protection" not in text:
                weak.append("ci_release_gates_branch_protection_keywords")
    return {
        "ok": not missing and not weak,
        "missing_files": missing,
        "weak_hints": weak,
    }


def run_github_protection_inprocess(
    repo: str, branch: str, token: str | None
) -> dict[str, Any]:
    e, meta = github_branch_run(repo, branch, None, token)
    return {
        "status": e.status,
        "meta": meta,
        "result": {k: v for k, v in asdict(e).items()},
    }


def _remote_decision(gh_status: str, missing_checks: list[str]) -> str:
    if gh_status == "PASS" and not missing_checks:
        return "verified"
    if gh_status == "FAIL":
        return "failed"
    return "not_enough_evidence"


def assess_external_template(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != SCHEMA_V:
        failures.append("schema")
    if payload.get("status") != "verified":
        failures.append("status")
    for k in ("reviewed_by", "reviewed_at", "git_host", "repository", "default_branch"):
        if _missing_templ(payload.get(k)):
            failures.append(k)
    gh = payload.get("github_settings") or {}
    for key, code in (
        ("required_status_checks_include_release_approval_gate", "req_checks"),
        ("required_pull_request_reviews_min_1", "pr_reviews"),
        ("no_force_push", "no_force_push"),
        ("no_branch_deletion", "no_delete"),
        ("admin_enforce_or_documented_exception", "admin"),
    ):
        if gh.get(key) is not True:
            failures.append(code)
    art = payload.get("artifacts") or {}
    for k in ("settings_export_or_screenshot_uri", "ci_workflow_run_green_reference"):
        if _missing_templ(art.get(k)):
            failures.append(k)
    saf = payload.get("safety") or {}
    if saf.get("no_secrets_in_export") is not True:
        failures.append("secrets")
    if saf.get("owner_signoff") is not True:
        failures.append("owner")
    return {"status": "PASS" if not failures else "FAIL", "failures": failures}


def build_report_payload(
    *,
    external_json: Path = DEFAULT_EXT,
    github_repo: str | None = None,
    github_branch: str = "main",
    github_token: str | None = None,
) -> dict[str, Any]:
    ci = analyze_ci_yml_mandatory_jobs()
    docs = analyze_doc_hints()
    ext_raw = external_json.read_text(encoding="utf-8")
    ext = assess_external_template(json.loads(ext_raw))

    repo = (github_repo or "").strip() or DEFAULT_GH_REPO
    ghp = run_github_protection_inprocess(repo, github_branch, github_token)
    expected_checks = ci.get("expected_required_checks", [])
    found_checks = ghp["result"].get("required_contexts", [])
    missing_checks = list(ghp["result"].get("missing_for_ci_yml", []) or [])
    remote_checked = ghp["status"] not in {"UNKNOWN_NO_GITHUB_AUTH", "UNKNOWN"}
    remote = {
        "checked_via_api": remote_checked,
        "expected_checks": expected_checks,
        "found_checks": found_checks,
        "missing_checks": missing_checks,
        "decision": _remote_decision(ghp["status"], missing_checks),
    }

    internal: list[str] = []
    if not ci.get("ok"):
        internal.append("ci_yml_missing_mandatory_jobs")
    if not docs.get("ok"):
        internal.append("branch_protection_docs_incomplete")

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "ci_workflow_mandatory_jobs": ci,
        "branch_protection_doc_surface": docs,
        "github_api_protection": ghp,
        "remote_branch_protection": remote,
        "external_template_assessment": ext,
        "internal_issues": internal,
        "external_required": [
            (
                "GitHub/Git-Host: Required Status Checks inkl. "
                "release-approval-gate, PR-Reviews, kein Force-Push; "
                "siehe branch_protection_evidence.template.json."
            ),
            (
                "Export oder Screenshot der Branch-Protection-Einstellungen "
                "ohne Secrets; Owner-Signoff."
            ),
        ],
        "notes": [
            (
                "API-Status UNKNOWN_NO_GITHUB_AUTH in CI/Agent erwartbar; "
                "kein FAIL der lokalen Repo-Checks."
            ),
            (
                "Lokale Pflicht: Job-Ids in ci.yml passen zu "
                "tools/check_github_branch_protection.MANDATORY."
            ),
        ],
    }


def render_md(p: dict[str, Any]) -> str:
    g = p["github_api_protection"]
    remote = p["remote_branch_protection"]
    return "\n".join(
        [
            "# Branch-Protection und CI Evidence Report",
            "",
            f"Erzeugt: `{p['generated_at']}` · SHA `{p['git_sha']}`",
            f"ci.yml Pflichtjobs: ok=`{p['ci_workflow_mandatory_jobs']['ok']}`",
            f"Doku/Hints: ok=`{p['branch_protection_doc_surface']['ok']}`",
            f"GitHub-API-Status: `{g['status']}` (meta={g.get('meta')!r})",
            f"Remote geprueft: `{str(remote['checked_via_api']).lower()}` · Entscheidung: `{remote['decision']}`",
            f"Erwartete Required Checks: `{len(remote['expected_checks'])}`",
            f"Gefundene Required Checks: `{len(remote['found_checks'])}`",
            f"Fehlende Required Checks: `{len(remote['missing_checks'])}`",
            f"externes Template: `{p['external_template_assessment']['status']}`",
            f"interne Blocker: {len(p['internal_issues'])}",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--external-json", type=Path, default=DEFAULT_EXT)
    ap.add_argument("--github-repo", type=str, default=None)
    ap.add_argument("--github-branch", type=str, default="main")
    ap.add_argument(
        "--github-token",
        type=str,
        default=None,
        help="optional; sonst GITHUB_TOKEN/GH_TOKEN",
    )
    ap.add_argument("--output-md", type=Path)
    ap.add_argument("--output-json", type=Path)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 bei fehlenden Pflicht-Jobs in ci.yml oder Doku-Luecken.",
    )
    ap.add_argument(
        "--strict-external",
        action="store_true",
        help="Zusaetzlich: externes JSON muss assess PASS (verified) sein.",
    )
    a = ap.parse_args(argv)
    p = build_report_payload(
        external_json=a.external_json,
        github_repo=a.github_repo,
        github_branch=a.github_branch,
        github_token=a.github_token,
    )
    if a.output_json:
        a.output_json.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(p, indent=2, ensure_ascii=False)
        a.output_json.write_text(body, encoding="utf-8")
    if a.output_md:
        a.output_md.parent.mkdir(parents=True, exist_ok=True)
        a.output_md.write_text(render_md(p), encoding="utf-8")
    ghs = p["github_api_protection"]["status"]
    ets = p["external_template_assessment"]["status"]
    print(
        f"branch_protection_ci_evidence_report: internal={len(p['internal_issues'])} "
        f"gh={ghs} ext={ets}"
    )
    if a.strict and p["internal_issues"]:
        return 1
    if a.strict_external and p["external_template_assessment"]["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
