from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "production_readiness_audit.py"


def _load_audit_module():
    # Eindeutiger Name + sys.modules: sonst scheitert @dataclass bei
    # exec_module (cls.__module__ fehlt in sys.modules).
    name = f"production_readiness_audit_test_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_default_repo_audit_runs() -> None:
    p = _load_audit_module()
    d = p.run_audit(REPO, strict=False)
    assert d["ok"] is True
    assert d["ampel_global"] in ("GREEN", "YELLOW", "RED")
    assert len(d["categories"]) == 12
    ids = [c["id"] for c in d["categories"]]
    assert "github_branch_protection" in ids
    assert ids[0] == "ci_branch" and ids[1] == "github_branch_protection"


def test_strict_fails_on_real_repo_l4_l5_gaps() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, (r.stdout, r.stderr)


def test_strict_passes_synthetic_l4_l5_marks(tmp_path: Path) -> None:
    p = _load_audit_module()
    root = tmp_path / "repo"
    (root / "docs" / "production_10_10").mkdir(parents=True)
    shutil.copy(
        REPO / "docs/production_10_10/readiness_evidence_schema.json",
        root / "docs/production_10_10/readiness_evidence_schema.json",
    )
    d_ev = root / "docs" / "release_evidence"
    d_ev.mkdir(parents=True)
    lines = [
        "readiness_mark: L4  category=disaster_recovery",
        "readiness_mark: L4  category=shadow_burn_in",
        "readiness_mark: L4  category=security_audit",
        "readiness_mark: L4  category=secrets_vault",
        "readiness_mark: L4  category=alert_routing",
        "readiness_mark: L4  category=customer_ui",
        "readiness_mark: L4  category=live_mirror",
        "readiness_mark: L4  category=performance_alpha",
        "readiness_mark: L4  category=release_evidence",
    ]
    (d_ev / "L4_bundle.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (d_ev / "L5_compliance.md").write_text(
        "readiness_mark: L5  category=compliance\n",
        encoding="utf-8",
    )
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "\n".join(
            [
                "on: [push]",
                "jobs:",
                "  t:",
                "    runs-on: ubuntu-latest",
                "    steps:",
                "    - run: check_release_approval_gates",
                "    - run: python -m pytest",
                "    - run: pip_audit_supply_chain_gate",
                "    - run: check_production_env_template_security",
                "    - run: pnpm e2e",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "migrations.md").write_text("restore and pitr backup", encoding="utf-8")
    (root / "docs" / "db-schema.md").write_text("schema", encoding="utf-8")
    (root / "docs" / "EXTERNAL_GO_LIVE_DEPENDENCIES.md").write_text(
        "x" * 201, encoding="utf-8"
    )
    (root / "docs" / "shadow_burn_in_ramp.md").write_text("burnin", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "verify_shadow_burn_in.py").write_text("# x", encoding="utf-8")
    (root / "docs" / "LaunchChecklist.md").write_text("LIVE_REQUIRE", encoding="utf-8")
    (root / "services" / "alert-engine" / "src").mkdir(parents=True)
    (root / "services" / "monitor-engine" / "src").mkdir(parents=True)
    (root / "services" / "live-broker" / "src").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "tools" / "check_release_approval_gates.py").write_text("x", encoding="utf-8")
    (root / "tools" / "check_coverage_gates.py").write_text("x", encoding="utf-8")
    (root / "tools" / "validate_env_profile.py").write_text("x", encoding="utf-8")
    (root / "tools" / "check_production_env_template_security.py").write_text(
        "x", encoding="utf-8"
    )
    tdir = root / "tests" / "unit" / "alert"
    tdir.mkdir(parents=True)
    (tdir / "test_foo.py").write_text("def test_x(): pass", encoding="utf-8")
    (root / "tests" / "live_broker_smoke.py").write_text("def t(): pass", encoding="utf-8")
    (root / "apps" / "dashboard" / "src").mkdir(parents=True)

    dct = p.run_audit(root, strict=True)
    assert dct["strict_ok"] is True, json.dumps(dct, indent=2)[:2000]
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict", "--repo-root", str(root)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_markdown_and_json_together(tmp_path: Path) -> None:
    pout = tmp_path / "r.md"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--report-md", str(pout), "--summary-json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    j = json.loads(r.stdout)
    assert j.get("ok") is True
    t = pout.read_text(encoding="utf-8")
    assert "Production-Readiness-Audit" in t
    assert "| Ampel |" in t
