from __future__ import annotations

import json

import scripts.demo_trading_evidence_report as mod
from scripts.bitget_demo_readiness import DemoReadiness


def _rep(result: str, *, executed: bool = False) -> DemoReadiness:
    return DemoReadiness(
        result=result,
        blockers=[] if result != "FAIL" else ["blocked"],
        warnings=[],
        checks={"demo_order_executed": "true" if executed else "false"},
        env_snapshot={},
    )


def test_demo_evidence_ready_never_allows_live(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_build_report(env, mode, **kwargs):  # type: ignore[no-untyped-def]
        if mode == "private-readonly":
            return _rep("PASS")
        if mode == "demo-order-dry-run":
            return _rep("PASS")
        return _rep("PASS")

    monkeypatch.setattr(mod, "build_report", fake_build_report)
    evidence = mod.build_evidence(
        {},
        run_private_readonly=True,
        run_order_dry_run=True,
        run_order_smoke=False,
        allow_demo_money=False,
    )
    assert evidence.result == "DEMO_READY"
    assert evidence.live_trading_allowed is False
    assert evidence.checks["private_live_allowed"] == "false"


def test_demo_evidence_verified_still_never_allows_live(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_build_report(env, mode, **kwargs):  # type: ignore[no-untyped-def]
        if mode == "demo-order-smoke":
            return _rep("PASS", executed=True)
        return _rep("PASS")

    monkeypatch.setattr(mod, "build_report", fake_build_report)
    evidence = mod.build_evidence(
        {},
        run_private_readonly=True,
        run_order_dry_run=True,
        run_order_smoke=True,
        allow_demo_money=True,
    )
    assert evidence.result == "DEMO_VERIFIED"
    assert evidence.demo_verified is True
    assert evidence.live_trading_allowed is False
    assert evidence.checks["private_live_allowed"] == "false"


def test_demo_evidence_failed_on_blocker(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_build_report(env, mode, **kwargs):  # type: ignore[no-untyped-def]
        return _rep("FAIL")

    monkeypatch.setattr(mod, "build_report", fake_build_report)
    evidence = mod.build_evidence(
        {},
        run_private_readonly=True,
        run_order_dry_run=True,
        run_order_smoke=False,
        allow_demo_money=False,
    )
    assert evidence.result == "FAILED"
    assert evidence.live_trading_allowed is False
    assert evidence.blockers


def test_archive_success_writes_verified_copies(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    def fake_build_report(env, mode, **kwargs):  # type: ignore[no-untyped-def]
        if mode == "demo-order-smoke":
            return _rep("PASS", executed=True)
        return _rep("PASS")

    monkeypatch.setattr(mod, "build_report", fake_build_report)
    env_file = tmp_path / ".env.demo"
    env_file.write_text("EXECUTION_MODE=bitget_demo\n", encoding="utf-8")
    out_md = tmp_path / "demo_trading_evidence.md"
    out_json = tmp_path / "demo_trading_evidence.json"
    rc = mod.main(
        [
            "--env-file",
            str(env_file),
            "--private-readonly",
            "--order-dry-run",
            "--demo-order-smoke",
            "--i-understand-this-uses-demo-money",
            "--archive-success",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ]
    )
    assert rc == 0
    assert (tmp_path / "demo_trading_evidence_DEMO_VERIFIED.md").exists()
    assert (tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json").exists()
    ts_files = list(tmp_path.glob("demo_trading_evidence_DEMO_VERIFIED_*.json"))
    assert ts_files
    parsed = json.loads(out_json.read_text(encoding="utf-8"))
    assert parsed["checks"]["live_trading_allowed"] == "false"
