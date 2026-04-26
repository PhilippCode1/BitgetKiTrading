"""Vertrag: docs/ci_release_gates.md nennt dieselben GitHub Required-Check-Namen wie jobs.*.name in ci.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.check_github_branch_protection import MANDATORY

ROOT = Path(__file__).resolve().parents[3]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
DOC = ROOT / "docs" / "ci_release_gates.md"
WORKFLOW_NAME = "ci"


def _job_display_names() -> dict[str, str]:
    data = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    jobs = data.get("jobs")
    assert isinstance(jobs, dict), "ci.yml: jobs muss Mapping sein"
    out: dict[str, str] = {}
    for job_id, spec in jobs.items():
        if not isinstance(spec, dict):
            continue
        name = spec.get("name")
        out[job_id] = str(name).strip() if isinstance(name, str) and name.strip() else job_id
    return out


def test_ci_release_gates_doc_exists() -> None:
    assert DOC.is_file(), f"fehlt {DOC}"


def test_ci_release_gates_lists_exact_github_check_names() -> None:
    """GitHub zeigt 'workflow_name / job.name', nicht die YAML-Job-Id."""
    displays = _job_display_names()
    text = DOC.read_text(encoding="utf-8")
    missing: list[str] = []
    for job_id in MANDATORY:
        display = displays.get(job_id)
        assert display, f"ci.yml: Job {job_id!r} fehlt oder hat keinen Namen"
        needle = f"{WORKFLOW_NAME} / {display}"
        if needle not in text:
            missing.append(needle)
    assert not missing, (
        "docs/ci_release_gates.md muss exakte Status-Check-Strings aus ci.yml enthalten "
        f"(Branch-Protection): fehlt {missing}"
    )


def test_ci_release_gates_references_branch_protection_tooling() -> None:
    text = DOC.read_text(encoding="utf-8")
    for path in (
        "tools/check_github_branch_protection.py",
        "scripts/branch_protection_ci_evidence_report.py",
        "tools/check_release_approval_gates.py",
    ):
        assert path in text, f"Doku muss {path} fuer Merge-Gates nennen"
