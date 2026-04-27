"""Regression: CI muss 10/10-Matrix-Validator und Live-Broker-Preflight strikt ausfuehren."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_python_job_includes_matrix_and_preflight_gates() -> None:
    text = CI_YML.read_text(encoding="utf-8")
    assert "check_10_10_evidence.py" in text, "CI muss tools/check_10_10_evidence.py ausfuehren"
    assert "check_live_broker_preflight.py" in text, "CI muss Live-Broker-Preflight strikt ausfuehren"
    assert "Evidence-Matrix 10/10" in text or "check_10_10_evidence" in text
    assert "--check-report" in text, "CI muss evidence_status_report.md gegen die Matrix pruefen"
    assert "evidence_status_report.md" in text
    assert "--strict" in text


def test_ci_evidence_matrix_step_before_live_broker_preflight() -> None:
    """Evidence-Matrix (Drift/Schema) muss vor Live-Broker-Preflight laufen (Gate-Reihenfolge)."""
    text = CI_YML.read_text(encoding="utf-8")
    step_em = text.find("- name: Evidence-Matrix 10/10")
    step_lb = text.find("- name: Live-Broker Preflight-Matrix")
    assert step_em != -1, "Step Evidence-Matrix 10/10 fehlt"
    assert step_lb != -1, "Step Live-Broker Preflight-Matrix fehlt"
    assert step_em < step_lb, "Evidence-Matrix muss vor Live-Broker-Preflight stehen"
    c10 = text.find("check_10_10_evidence.py")
    lbp = text.find("check_live_broker_preflight.py")
    assert c10 < lbp, "check_10_10_evidence.py muss vor check_live_broker_preflight.py vorkommen"


def test_ci_python_job_ruff_step_includes_ai_operator_assistant_safety() -> None:
    """LLM-Safety: execution_authority-Schema/Guards duerfen nicht aus dem blockierenden Ruff-Schritt fallen."""
    text = CI_YML.read_text(encoding="utf-8")
    ruff = text.find("- name: Ruff")
    assert ruff != -1, "Ruff-Step fehlt im Python-Job"
    nxt = text.find("\n      - name:", ruff + 1)
    assert nxt != -1, "Ruff-Step ohne nachfolgenden Step (unerwartetes ci.yml)"
    chunk = text[ruff:nxt]
    assert "ruff check" in chunk
    assert "check_ai_operator_assistant_safety.py" in chunk, (
        "Ruff muss tools/check_ai_operator_assistant_safety.py linten (CI-Regressionsschutz)"
    )


def test_ci_python_job_ruff_step_lints_ci_workflow_contract_tests() -> None:
    """Regression: CI-Workflow-Contract-Tests muessen im gleichen Ruff-Lauf wie die Gates liegen (kein Drift unentdeckt)."""
    text = CI_YML.read_text(encoding="utf-8")
    ruff = text.find("- name: Ruff")
    assert ruff != -1
    nxt = text.find("\n      - name:", ruff + 1)
    assert nxt != -1
    chunk = text[ruff:nxt]
    assert "tests/tools/test_ci_workflow_evidence_gates.py" in chunk
    assert "tests/tools/test_ci_yml_mandatory_jobs_contract.py" in chunk


def test_ci_validates_shadow_and_production_env_templates() -> None:
    """P0 env_secrets_profiles: Template-Validierung muss in CI blockieren (kein Localhost in Prod-URLs, Platzhalter)."""
    text = CI_YML.read_text(encoding="utf-8")
    assert ".env.shadow.example" in text
    assert ".env.production.example" in text
    assert "validate_env_profile.py" in text
    assert "--profile shadow" in text and "--template" in text
    assert "--profile production" in text


def test_ci_python_job_runs_production_env_template_security_after_install_packages() -> None:
    """P0: Gate muss in echter Repo-Python-Umgebung laufen (nach setup-python + pinned deps)."""
    text = CI_YML.read_text(encoding="utf-8")
    assert "check_production_env_template_security.py" in text
    sec = text.find("check_production_env_template_security.py")
    install = text.find('name: "Install packages (gepinnt: requirements-dev + editables)"')
    assert sec != -1, "check_production_env_template_security.py muss in ci.yml vorkommen"
    assert install != -1, "Install-Step muss in ci.yml vorkommen"
    assert sec > install, "ENV-Template-Security-Gate soll nach Install packages (Python-Job) stehen"


def test_ci_python_job_release_sanity_after_install_packages() -> None:
    """Release-Sanity soll in derselben installierten Repo-Umgebung wie die weiteren Python-Gates laufen."""
    text = CI_YML.read_text(encoding="utf-8")
    rs = text.find("release_sanity_checks.py")
    install = text.find('name: "Install packages (gepinnt: requirements-dev + editables)"')
    assert rs != -1, "release_sanity_checks.py muss in ci.yml vorkommen"
    assert install != -1, "Install-Step muss in ci.yml vorkommen"
    assert rs > install, "Release-Sanity soll nach Install packages (Python-Job) stehen"


def test_ci_compose_healthcheck_uses_local_publish_overlay() -> None:
    """Regression: E2E-Stack muss Basis + local-publish mergen (wie docs/compose_runtime.md, nicht nur docker-compose.yml)."""
    text = CI_YML.read_text(encoding="utf-8")
    start = text.find("  compose_healthcheck:")
    assert start != -1, "Job compose_healthcheck fehlt in ci.yml"
    end = text.find("  release-approval-gate:", start)
    assert end != -1, "Job release-approval-gate muss nach compose_healthcheck folgen"
    chunk = text[start:end]
    assert "docker-compose.local-publish.yml" in chunk
    assert chunk.count("docker-compose.local-publish.yml") >= 2, (
        "Erwartet: config-validate und up nutzen beide das Overlay"
    )
    assert "config --quiet" in chunk
    assert "up -d --build" in chunk


def test_ci_release_approval_gate_runs_check_release_approval_gates() -> None:
    """Merge-Gate: P0/P1 OPEN in REPO_FREEZE_GAP_MATRIX + Versions-Einheit darf nicht aus ci.yml fallen."""
    text = CI_YML.read_text(encoding="utf-8")
    start = text.find("  release-approval-gate:")
    assert start != -1, "Job release-approval-gate fehlt in ci.yml"
    chunk = text[start:]
    assert "check_release_approval_gates.py" in chunk, (
        "release-approval-gate muss tools/check_release_approval_gates.py ausfuehren"
    )
    assert "needs:" in chunk
    assert "python" in chunk
    assert "dashboard" in chunk
    assert "compose_healthcheck" in chunk
