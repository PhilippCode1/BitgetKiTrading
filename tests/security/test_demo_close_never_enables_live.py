from __future__ import annotations

import scripts.demo_reconcile_evidence_report as mod


def _env() -> dict[str, str]:
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


def test_demo_close_report_never_enables_live() -> None:
    report = mod.build_reconcile_report(
        _env(), "close-smoke", allow_close_demo_position=False
    )
    assert report.live_trading_allowed is False
    assert report.private_live_allowed is False
    assert report.checks["live_trading_allowed"] == "false"
    assert report.checks["private_live_allowed"] == "false"
