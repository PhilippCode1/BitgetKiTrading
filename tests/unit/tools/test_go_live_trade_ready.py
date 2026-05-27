from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "go_live_trade_ready.py"


def _load_module():
    name = f"go_live_trade_ready_test_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_template_reports_code_ready_not_trade_ready() -> None:
    mod = _load_module()
    report = mod.evaluate_trade_ready(
        env_file=REPO / ".env.production.example",
        strict_runtime=False,
        skip_audit=True,
    )
    assert report["code_ready"] is True
    assert report["trade_ready"] is False


def test_strict_example_env_not_trade_ready() -> None:
    mod = _load_module()
    report = mod.evaluate_trade_ready(
        env_file=REPO / ".env.production.example",
        strict_runtime=True,
        skip_audit=True,
    )
    assert report["code_ready"] is True
    assert report["trade_ready"] is False
    assert report["failing_steps"]


def test_prioritize_env_keys_groups_vault_first() -> None:
    mod = _load_module()
    groups = mod.prioritize_env_keys(
        ["VAULT_TOKEN", "OIDC_CLIENT_ID", "REDIS_PASSWORD", "FOO_BAR"]
    )
    assert "VAULT_TOKEN" in groups["p0_vault"]
    assert "OIDC_CLIENT_ID" in groups["p1_oidc_portal"]
    assert "REDIS_PASSWORD" in groups["p2_infra"]
    assert "FOO_BAR" in groups["other"]
