from __future__ import annotations

import json

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
        "BITGET_SYMBOL": "BTCUSDT",
        "DEMO_RECONCILE_SYMBOL": "BTCUSDT",
        "DEMO_DEFAULT_PRODUCT_TYPE": "USDT-FUTURES",
    }


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        pass

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def get(self, url):  # type: ignore[no-untyped-def]
        class _R:
            status_code = 200

        return _R()


def _patch_basics(monkeypatch, positions, open_orders=None) -> None:  # type: ignore[no-untyped-def]
    if open_orders is None:
        open_orders = []

    def fake_get(client, env, path, query):  # type: ignore[no-untyped-def]
        if path.endswith("/account/accounts"):
            return 200, {"code": "00000", "data": [{"assetMode": "single"}]}
        if path.endswith("/position/all-position"):
            return 200, {"code": "00000", "data": positions}
        if path.endswith("/orders-pending"):
            return 200, {"code": "00000", "data": open_orders}
        if path.endswith("/orders-history"):
            return 200, {"code": "00000", "data": []}
        return 404, {"code": "404", "msg": "not found"}

    monkeypatch.setattr(mod.httpx, "Client", _FakeClient)
    monkeypatch.setattr(mod, "_private_get", fake_get)


def test_readonly_sendet_keine_order(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_basics(monkeypatch, positions=[])
    sent = {"count": 0}

    def fake_post(client, env, path, body):  # type: ignore[no-untyped-def]
        sent["count"] += 1
        return 200, {"code": "00000", "msg": "success"}

    monkeypatch.setattr(mod, "_private_post", fake_post)
    report = mod.build_reconcile_report(_env(), "readonly")
    assert sent["count"] == 0
    assert report.checks["live_trading_allowed"] == "false"
    assert report.checks["private_live_allowed"] == "false"


def test_close_dry_run_sendet_keine_order(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_basics(
        monkeypatch,
        positions=[
            {
                "symbol": "BTCUSDT",
                "holdSide": "long",
                "total": "0.0001",
                "marginCoin": "USDT",
            }
        ],
    )
    sent = {"count": 0}

    def fake_post(client, env, path, body):  # type: ignore[no-untyped-def]
        sent["count"] += 1
        return 200, {"code": "00000", "msg": "success"}

    monkeypatch.setattr(mod, "_private_post", fake_post)
    report = mod.build_reconcile_report(_env(), "close-dry-run")
    assert sent["count"] == 0
    assert report.reconcile_status == "CLOSE_READY"


def test_close_smoke_ohne_flag_blockiert(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_basics(monkeypatch, positions=[])
    report = mod.build_reconcile_report(
        _env(), "close-smoke", allow_close_demo_position=False
    )
    assert report.result == "FAILED"
    assert any("Close-Smoke braucht Flag" in b for b in report.blockers)


def test_close_payload_for_hedge_long(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["DEMO_CLOSE_POSITION_ENABLE"] = "true"
    _patch_basics(
        monkeypatch,
        positions=[
            {
                "symbol": "BTCUSDT",
                "holdSide": "long",
                "total": "0.0001",
                "marginCoin": "USDT",
            }
        ],
    )
    captured = {"payload": {}}

    def fake_post(client, env, path, body):  # type: ignore[no-untyped-def]
        captured["payload"] = body
        return 200, {"code": "00000", "msg": "success"}

    monkeypatch.setattr(mod, "_private_post", fake_post)
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "CLOSE_VERIFIED"
    assert captured["payload"]["side"] == "buy"
    assert captured["payload"]["tradeSide"] == "close"
    assert captured["payload"]["tradeSide"] != "open"


def test_close_payload_for_hedge_short(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["DEMO_CLOSE_POSITION_ENABLE"] = "true"
    _patch_basics(
        monkeypatch,
        positions=[
            {
                "symbol": "BTCUSDT",
                "holdSide": "short",
                "total": "0.0001",
                "marginCoin": "USDT",
            }
        ],
    )
    captured = {"payload": {}}

    def fake_post(client, env, path, body):  # type: ignore[no-untyped-def]
        captured["payload"] = body
        return 200, {"code": "00000", "msg": "success"}

    monkeypatch.setattr(mod, "_private_post", fake_post)
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "CLOSE_VERIFIED"
    assert captured["payload"]["side"] == "sell"
    assert captured["payload"]["tradeSide"] == "close"
    assert report.checks["live_trading_allowed"] == "false"
    assert report.checks["private_live_allowed"] == "false"


def test_one_way_long_close_payload_uses_sell_reduce_only() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "one_way"
    payload = mod.build_close_order_payload(
        env,
        {
            "symbol": "BTCUSDT",
            "holdSide": "long",
            "total": "0.0001",
            "marginCoin": "USDT",
        },
    )
    assert payload["side"] == "sell"
    assert payload["reduceOnly"] == "YES"
    assert "tradeSide" not in payload


def test_one_way_short_close_payload_uses_buy_reduce_only() -> None:
    env = _env()
    env["DEMO_POSITION_MODE"] = "one_way"
    payload = mod.build_close_order_payload(
        env,
        {
            "symbol": "BTCUSDT",
            "holdSide": "short",
            "total": "0.0001",
            "marginCoin": "USDT",
        },
    )
    assert payload["side"] == "buy"
    assert payload["reduceOnly"] == "YES"
    assert "tradeSide" not in payload


def test_close_smoke_blocks_without_enable_when_position_exists(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["DEMO_CLOSE_POSITION_ENABLE"] = "false"
    _patch_basics(
        monkeypatch,
        positions=[
            {
                "symbol": "BTCUSDT",
                "holdSide": "long",
                "total": "0.0001",
                "marginCoin": "USDT",
            }
        ],
    )
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "FAILED"
    assert any("DEMO_CLOSE_POSITION_ENABLE" in b for b in report.blockers)


def test_close_smoke_blocks_when_live_trade_enable_true(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["LIVE_TRADE_ENABLE"] = "true"
    _patch_basics(monkeypatch, positions=[])
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "FAILED"
    assert any("LIVE_TRADE_ENABLE muss false sein." in b for b in report.blockers)


def test_close_smoke_blocks_when_live_keys_present(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["BITGET_API_KEY"] = "live-key"
    _patch_basics(monkeypatch, positions=[])
    report = mod.build_reconcile_report(
        env, "close-smoke", allow_close_demo_position=True
    )
    assert report.result == "FAILED"
    assert any("Live-Credentials" in b for b in report.blockers)


def test_report_contains_no_secret(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_basics(monkeypatch, positions=[])
    report = mod.build_reconcile_report(_env(), "readonly")
    md = mod.to_markdown(report)
    assert "demo-secret" not in md


def test_archive_success_writes_close_verified_copies(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    env["DEMO_CLOSE_POSITION_ENABLE"] = "true"
    _patch_basics(
        monkeypatch,
        positions=[
            {
                "symbol": "BTCUSDT",
                "holdSide": "long",
                "total": "0.0001",
                "marginCoin": "USDT",
            }
        ],
    )
    monkeypatch.setattr(mod, "load_dotenv", lambda _: env)

    def fake_post(client, env, path, body):  # type: ignore[no-untyped-def]
        return 200, {"code": "00000", "msg": "success"}

    monkeypatch.setattr(mod, "_private_post", fake_post)
    env_file = tmp_path / ".env.demo"
    env_file.write_text("EXECUTION_MODE=bitget_demo\n", encoding="utf-8")
    out_md = tmp_path / "demo_reconcile_evidence.md"
    out_json = tmp_path / "demo_reconcile_evidence.json"
    rc = mod.main(
        [
            "--env-file",
            str(env_file),
            "--mode",
            "close-smoke",
            "--i-understand-this-closes-demo-position",
            "--archive-success",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ]
    )
    assert rc == 0
    assert (tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json").exists()
    assert list(tmp_path.glob("demo_reconcile_evidence_CLOSE_VERIFIED_*.json"))


def test_archive_success_writes_clean_copies(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env = _env()
    _patch_basics(monkeypatch, positions=[])
    monkeypatch.setattr(mod, "load_dotenv", lambda _: env)
    env_file = tmp_path / ".env.demo"
    env_file.write_text("EXECUTION_MODE=bitget_demo\n", encoding="utf-8")
    out_md = tmp_path / "demo_reconcile_evidence.md"
    out_json = tmp_path / "demo_reconcile_evidence.json"
    rc = mod.main(
        [
            "--env-file",
            str(env_file),
            "--mode",
            "readonly",
            "--archive-success",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ]
    )
    assert rc == 0
    assert (tmp_path / "demo_reconcile_evidence_CLEAN.json").exists()
    parsed = json.loads(
        (tmp_path / "demo_reconcile_evidence_CLEAN.json").read_text(encoding="utf-8")
    )
    assert parsed["checks"]["private_live_allowed"] == "false"
