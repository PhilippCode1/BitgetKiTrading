from __future__ import annotations

from scripts.bitget_demo_readiness import build_report


def test_demo_order_block_ohne_demo_modus() -> None:
    env = {
        "EXECUTION_MODE": "paper",
        "LIVE_TRADE_ENABLE": "false",
        "BITGET_DEMO_ENABLED": "false",
        "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
    }
    report = build_report(env, mode="dry-run")
    assert report.result == "FAIL"
    assert any("bitget_demo" in b for b in [x.lower() for x in report.blockers])


def test_demo_order_block_mit_live_flag() -> None:
    env = {
        "EXECUTION_MODE": "bitget_demo",
        "LIVE_TRADE_ENABLE": "true",
        "BITGET_DEMO_ENABLED": "true",
        "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
        "BITGET_DEMO_API_KEY": "k",
        "BITGET_DEMO_API_SECRET": "s",
        "BITGET_DEMO_API_PASSPHRASE": "p",
    }
    report = build_report(env, mode="dry-run")
    assert report.result == "FAIL"
