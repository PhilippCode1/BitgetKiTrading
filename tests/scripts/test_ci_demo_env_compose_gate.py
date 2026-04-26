from __future__ import annotations

import json
from pathlib import Path

import scripts.ci_demo_env_compose_gate as mod


def _write_env(path: Path, extra: dict[str, str] | None = None) -> None:
    payload = {
        "EXECUTION_MODE": "bitget_demo",
        "LIVE_TRADE_ENABLE": "false",
        "BITGET_DEMO_ENABLED": "true",
        "DEMO_ORDER_SUBMIT_ENABLE": "false",
        "DEMO_CLOSE_POSITION_ENABLE": "false",
        "BITGET_DEMO_PAPTRADING_HEADER": "1",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "FRONTEND_URL": "http://127.0.0.1:3000",
        "CORS_ALLOW_ORIGINS": "http://127.0.0.1:3000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
        "POSTGRES_PASSWORD": "postgres",
        "GRAFANA_ADMIN_PASSWORD": "admin",
        "BITGET_API_KEY": "",
        "BITGET_API_SECRET": "",
        "BITGET_API_PASSPHRASE": "",
        "BITGET_DEMO_API_KEY": "<SET_ME>",
        "BITGET_DEMO_API_SECRET": "<SET_ME>",
        "BITGET_DEMO_API_PASSPHRASE": "<SET_ME>",
        "private_live_allowed": "false",
        "full_autonomous_live": "false",
    }
    if extra:
        payload.update(extra)
    lines = [f"{k}={v}" for k, v in payload.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_commands(monkeypatch, *, compose_available: bool = True) -> None:  # type: ignore[no-untyped-def]
    def fake_run(args, cwd=None):  # type: ignore[no-untyped-def]
        cmd = " ".join(args)
        if cmd.startswith("git ls-files"):
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        if cmd == "docker compose version":
            return type("R", (), {"returncode": 0 if compose_available else 1, "stdout": "", "stderr": ""})()
        if "config --services" in cmd:
            return type("R", (), {"returncode": 0, "stdout": "api-gateway\n", "stderr": ""})()
        if cmd.endswith("docker compose --env-file " + str(cwd / ".env.demo.example") + " config"):
            return type("R", (), {"returncode": 0, "stdout": "services:\n", "stderr": ""})()
        if "docker compose" in cmd and " config" in cmd:
            return type("R", (), {"returncode": 0, "stdout": "services:\n", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(mod, "_run_command", fake_run)


def test_missing_env_file_fails(tmp_path: Path) -> None:
    rep = mod.build_gate_report(tmp_path / ".env.demo.example")
    assert rep.result == "FAIL"


def test_missing_required_variable_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"APP_BASE_URL": ""})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"


def test_live_trade_enable_true_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"LIVE_TRADE_ENABLE": "true"})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"


def test_demo_order_submit_enable_true_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"DEMO_ORDER_SUBMIT_ENABLE": "true"})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"


def test_demo_close_position_enable_true_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"DEMO_CLOSE_POSITION_ENABLE": "true"})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"


def test_live_key_value_in_demo_profile_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"BITGET_API_KEY": "live_secret_key"})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"


def test_placeholder_demo_secrets_are_allowed(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(
        env_file,
        {
            "BITGET_DEMO_API_KEY": "<SET_ME>",
            "BITGET_DEMO_API_SECRET": "CHANGE_ME_IN_SECRET_STORE",
            "BITGET_DEMO_API_PASSPHRASE": "example-only",
        },
    )
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "PASS"


def test_script_writes_markdown_and_json(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    out_md = tmp_path / "gate.md"
    out_json = tmp_path / "gate.json"
    _write_env(env_file)
    _patch_commands(monkeypatch)
    rc = mod.main(
        [
            "--env-file",
            str(env_file),
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ]
    )
    assert rc == 0
    assert out_md.exists()
    assert out_json.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["result"] == "PASS"


def test_private_live_allowed_never_true(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"private_live_allowed": "true"})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"


def test_full_autonomous_live_never_true(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_file = tmp_path / ".env.demo.example"
    _write_env(env_file, {"full_autonomous_live": "true"})
    _patch_commands(monkeypatch)
    rep = mod.build_gate_report(env_file)
    assert rep.result == "FAIL"
