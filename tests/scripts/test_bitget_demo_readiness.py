from __future__ import annotations

from scripts.bitget_demo_readiness import build_report, to_markdown


def _env() -> dict[str, str]:
    return {
        "EXECUTION_MODE": "bitget_demo",
        "LIVE_TRADE_ENABLE": "false",
        "BITGET_DEMO_ENABLED": "true",
        "BITGET_API_BASE_URL": "https://api.bitget.com",
        "BITGET_DEMO_REST_BASE_URL": "https://api.bitget.com",
        "BITGET_DEMO_API_KEY": "demo-key",
        "BITGET_DEMO_API_SECRET": "demo-secret",
        "BITGET_DEMO_API_PASSPHRASE": "demo-pass",
        "BITGET_DEMO_PAPTRADING_HEADER": "1",
        "DEMO_ORDER_SUBMIT_ENABLE": "false",
        "DEMO_ALLOWED_SYMBOLS": "BTCUSDT,ETHUSDT",
        "BITGET_SYMBOL": "BTCUSDT",
    }


def test_demo_readiness_blocks_live_trade_enable_true() -> None:
    env = _env()
    env["LIVE_TRADE_ENABLE"] = "true"
    report = build_report(env, mode="dry-run")
    assert report.result == "FAIL"
    assert any("LIVE_TRADE_ENABLE" in b for b in report.blockers)


def test_demo_readiness_blocks_execution_mode_live() -> None:
    env = _env()
    env["EXECUTION_MODE"] = "live"
    report = build_report(env, mode="dry-run")
    assert report.result == "FAIL"


def test_demo_readiness_redacts_secrets_in_markdown() -> None:
    env = _env()
    report = build_report(env, mode="dry-run")
    md = to_markdown(report)
    assert "demo-secret" not in md
    assert "set_redacted" in md


def test_demo_order_smoke_requires_explicit_flag() -> None:
    env = _env()
    env["DEMO_ORDER_SUBMIT_ENABLE"] = "true"
    report = build_report(env, mode="demo-order-smoke", allow_demo_money=False)
    assert report.result == "FAIL"
    assert any("Demo-Order-Smoke braucht Flag" in b for b in report.blockers)


def test_demo_order_dry_run_never_executes_order() -> None:
    env = _env()
    report = build_report(env, mode="demo-order-dry-run")
    assert report.checks["demo_order_executed"] == "false"
    assert "demo_order_payload" in report.checks


def test_demo_readiness_blocks_missing_paptrading_header() -> None:
    env = _env()
    env["BITGET_DEMO_PAPTRADING_HEADER"] = ""
    report = build_report(env, mode="dry-run")
    assert report.result == "FAIL"
    assert any("PAPTRADING" in b.upper() for b in report.blockers)
