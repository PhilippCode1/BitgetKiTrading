from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "go_live_ops_wizard.py"


def _load_module():
    name = f"go_live_ops_wizard_test_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_apply_safe_generates_redis_password(tmp_path: Path) -> None:
    mod = _load_module()
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "REDIS_PASSWORD=YOUR_API_KEY_HERE\nGATEWAY_JWT_SECRET=\n",
        encoding="utf-8",
    )
    applied = mod.apply_safe_fixes(env_file, vault_dev=False)
    env = mod._load_dotenv(env_file)
    assert "REDIS_PASSWORD (generated)" in applied
    assert not mod._is_placeholder(env["REDIS_PASSWORD"])


def test_apply_safe_merges_vault_dev(tmp_path: Path) -> None:
    mod = _load_module()
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "\n".join(
            (
                "VAULT_TOKEN=YOUR_API_KEY_HERE",
                "VAULT_SECRET_ID=YOUR_VALUE_HERE",
                "MODUL_MATE_GATE_TENANT_ID=<SET_OPERATOR_TENANT_ID>",
            )
        ),
        encoding="utf-8",
    )
    applied = mod.apply_safe_fixes(env_file, vault_dev=True)
    env = mod._load_dotenv(env_file)
    assert env["VAULT_TOKEN"] == "dev-root-token"
    assert env["MODUL_MATE_GATE_TENANT_ID"] == mod.DEV_TENANT_ID
    assert not mod._is_placeholder(env["VAULT_SECRET_ID"])
    assert any("VAULT_TOKEN" in a for a in applied)
