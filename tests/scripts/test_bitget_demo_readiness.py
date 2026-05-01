from __future__ import annotations

import scripts.bitget_demo_readiness as mod
from scripts.bitget_demo_readiness import (
    build_demo_order_body,
    build_report,
    to_markdown,
)


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


def test_one_way_payload_has_no_trade_side() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "one_way"
    body = build_demo_order_body(env)
    assert "tradeSide" not in body


def test_one_way_payload_has_no_pos_side() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "one_way"
    body = build_demo_order_body(env)
    assert "posSide" not in body


def test_one_way_payload_sets_reduce_only_no() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "one_way"
    body = build_demo_order_body(env)
    assert body.get("reduceOnly") == "NO"


def test_hedge_payload_sets_trade_side_open() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "hedge"
    env["DEMO_TRADE_SIDE"] = ""
    body = build_demo_order_body(env)
    assert body.get("tradeSide") == "open"


def test_hedge_payload_does_not_force_reduce_only_no() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "hedge"
    body = build_demo_order_body(env)
    assert "reduceOnly" not in body


def test_error_40774_sets_clear_hint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["DEMO_ORDER_SUBMIT_ENABLE"] = "true"

    def fake_private_post(client, env, path, body):  # type: ignore[no-untyped-def]
        return 400, {
            "code": "40774",
            "msg": "The order type for unilateral position must also be the unilateral position type.",
        }

    monkeypatch.setattr(mod, "_private_post", fake_private_post)
    report = build_report(env, mode="demo-order-smoke", allow_demo_money=True)
    assert report.result == "FAIL"
    assert report.checks["demo_order_code"] == "40774"
    assert (
        "Position-Mode und Order-Payload passen nicht zusammen"
        in report.checks["demo_order_hint"]
    )


def test_demo_order_smoke_blocked_without_safety_flag() -> None:
    env = _env()
    env["DEMO_ORDER_SUBMIT_ENABLE"] = "true"
    report = build_report(env, mode="demo-order-smoke", allow_demo_money=False)
    assert report.result == "FAIL"
    assert any("Demo-Order-Smoke braucht Flag" in b for b in report.blockers)


def test_demo_order_smoke_blocked_when_live_trade_enable_true() -> None:
    env = _env()
    env["DEMO_ORDER_SUBMIT_ENABLE"] = "true"
    env["LIVE_TRADE_ENABLE"] = "true"
    report = build_report(env, mode="demo-order-smoke", allow_demo_money=True)
    assert report.result == "FAIL"
    assert any("LIVE_TRADE_ENABLE muss false sein." in b for b in report.blockers)
