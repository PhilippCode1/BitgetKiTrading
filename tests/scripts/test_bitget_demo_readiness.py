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
