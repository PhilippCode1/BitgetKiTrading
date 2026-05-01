from __future__ import annotations

import scripts.demo_reconcile_evidence_report as mod


def _base_env() -> dict[str, str]:
    return {
        "EXECUTION_MODE": "bitget_demo",
        "LIVE_TRADE_ENABLE": "false",
        "BITGET_DEMO_ENABLED": "true",
        "BITGET_DEMO_PAPTRADING_HEADER": "1",
        "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
        "BITGET_DEMO_API_KEY": "demo-key",
        "BITGET_DEMO_API_SECRET": "demo-secret",
        "BITGET_DEMO_API_PASSPHRASE": "demo-pass",
        "BITGET_API_KEY": "",
        "BITGET_API_SECRET": "",
        "BITGET_API_PASSPHRASE": "",
    }


def test_close_smoke_requires_explicit_flag() -> None:
    report = mod.build_reconcile_report(
        _base_env(), "close-smoke", allow_close_demo_position=False
    )
    assert report.result == "FAILED"
    assert any("Close-Smoke braucht Flag" in b for b in report.blockers)


def test_close_smoke_blocks_with_live_trade_enable_true() -> None:
    env = _base_env()
    env["LIVE_TRADE_ENABLE"] = "true"
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "FAILED"
    assert any("LIVE_TRADE_ENABLE muss false sein." in b for b in report.blockers)


def test_close_smoke_blocks_with_live_keys_present() -> None:
    env = _base_env()
    env["BITGET_API_KEY"] = "live-key"
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "FAILED"
    assert any("Live-Credentials" in b for b in report.blockers)
