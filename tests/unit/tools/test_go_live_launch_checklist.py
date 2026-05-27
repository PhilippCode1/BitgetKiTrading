"""Go-Live Launch-Checklist orchestrator."""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "go_live_launch_checklist.py"


def _load_module():
    name = f"go_live_launch_checklist_test_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_template_launch_checklist_passes() -> None:
    mod = _load_module()
    steps, external = mod.run_launch_checklist(
        env_file=REPO / ".env.production.example",
        strict_runtime=False,
        skip_audit=True,
    )
    assert external
    errors = [s for s in steps if not s.ok]
    assert not errors, [(s.id, s.detail) for s in errors]


def test_strict_launch_checklist_skips_vault_for_placeholder_tenant() -> None:
    mod = _load_module()
    steps, _external = mod.run_launch_checklist(
        env_file=REPO / ".env.production.example",
        strict_runtime=True,
        skip_audit=True,
    )
    step_ids = [s.id for s in steps]
    assert "vault_tenant_credentials" not in step_ids


def test_strict_launch_checklist_includes_vault_step_with_real_tenant(
    tmp_path,
) -> None:
    mod = _load_module()
    env_file = tmp_path / "prod.env"
    env_file.write_text(
        "\n".join(
            (
                "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT=true",
                "MODUL_MATE_GATE_TENANT_ID=t-real-tenant",
                "VAULT_MODE=hashicorp",
                "VAULT_ADDR=https://vault.example.internal",
                "VAULT_TOKEN=YOUR_API_KEY_HERE",
            )
        ),
        encoding="utf-8",
    )
    steps, _external = mod.run_launch_checklist(
        env_file=env_file,
        strict_runtime=True,
        skip_audit=True,
    )
    step_ids = [s.id for s in steps]
    assert "vault_tenant_credentials" in step_ids
