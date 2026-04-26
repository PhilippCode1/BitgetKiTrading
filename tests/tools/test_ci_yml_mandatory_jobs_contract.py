"""Vertrag: MANDATORY-Job-Ids aus tools/check_github_branch_protection existieren in ci.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.check_github_branch_protection import MANDATORY

ROOT = Path(__file__).resolve().parents[2]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_yml_defines_all_mandatory_jobs_for_branch_protection() -> None:
    data = yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs")
    assert isinstance(jobs, dict), "ci.yml: root jobs muss ein Mapping sein"
    missing = [job_id for job_id in MANDATORY if job_id not in jobs]
    assert not missing, (
        "ci.yml fehlt Job(s), die check_github_branch_protection.MANDATORY verlangt: "
        f"{missing}. Gleiche .github/workflows/ci.yml, docs/ci_release_gates und das Tool an."
    )


def test_mandatory_ci_jobs_have_runs_on() -> None:
    """Branch-Protection-Checks referenzieren echte Jobs; jeder muss ausfuehrbar sein (runs-on)."""
    data = yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs")
    assert isinstance(jobs, dict)
    for job_id in MANDATORY:
        spec = jobs[job_id]
        assert isinstance(spec, dict), f"Job {job_id}: Mapping erwartet"
        ro = spec.get("runs-on")
        assert ro, f"Job {job_id}: runs-on fehlt oder ist leer"
