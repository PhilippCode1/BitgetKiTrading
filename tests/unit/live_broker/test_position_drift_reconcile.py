"""Prompt 27: Drift-Detector + Shadow-Sync (Ghost-Position) — Integration mit Mocks (kein Netz)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

from live_broker.config import LiveBrokerSettings
from live_broker.reconcile.position_drift import run_position_drift_once
from live_broker.private_rest import BitgetRestResponse


@dataclass
class InMemoryPosRepo:
    """Minimal live.positions-Stub fuer drift-Zyklus (ohne Postgres)."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    system_alerts: list[tuple[str, str, dict]] = field(default_factory=list)

    def list_live_positions(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.rows]

    def delete_live_position(self, inst_id: str, product_type: str, hold_side: str) -> bool:
        t = (inst_id.upper(), product_type.upper(), hold_side.lower())
        for i, r in enumerate(self.rows):
            if (
                str(r.get("inst_id", "")).upper() == t[0]
                and str(r.get("product_type", "")).upper() == t[1]
                and str(r.get("hold_side", "")).lower() == t[2]
            ):
                self.rows.pop(i)
                return True
        return False

    def upsert_live_position_from_bitget(
        self, row: dict[str, Any], *, notional_value: Any
    ) -> dict[str, Any]:
        raw = row.get("raw_json") or {}
        inst = str(row.get("inst_id") or "").upper()
        ptype = str(row.get("product_type") or "").upper()
        hside = str(row.get("hold_side") or "").lower()
        key = (inst, ptype, hside)
        self.rows = [
            r
            for r in self.rows
            if (
                str(r.get("inst_id", "")).upper(),
                str(r.get("product_type", "")).upper(),
                str(r.get("hold_side", "")).lower(),
            )
            != key
        ]
        d = {
            "inst_id": inst,
            "product_type": ptype,
            "hold_side": hside,
            "notional_value": notional_value,
            "raw_json": raw,
            "size_base": str(raw.get("total") or ""),
        }
        self.rows.append(d)
        return d


@dataclass
class _FakeRest:
    payload: dict[str, Any]

    def list_all_positions(self, *, priority: bool = True) -> BitgetRestResponse:  # noqa: ARG002
        return BitgetRestResponse(
            http_status=200,
            payload=self.payload,
            request_path="/api/v2/mix/position/all-position",
            method="GET",
            query_string="",
            body="",
            attempts=1,
        )


def _settings_ghost(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    env: dict[str, str] = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://t:t@127.0.0.1:1/t",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "shadow",
        "STRATEGY_EXEC_MODE": "manual",
        "SHADOW_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_API_KEY": "k",
        "BITGET_API_SECRET": "s",
        "BITGET_API_PASSPHRASE": "p",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def test_ghost_position_shadow_sync_one_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB-Zeile fehlt, Exchange meldet Position -> ein Drift-Lauf stellt live.positions her."""
    repo = InMemoryPosRepo()
    repo.rows.append(
        {
            "inst_id": "ZOMB",
            "product_type": "USDT-FUTURES",
            "hold_side": "short",
            "notional_value": "1",
            "raw_json": {},
            "size_base": "0.1",
        }
    )
    ex_item = {
        "instId": "ETHUSDT",
        "productType": "USDT-FUTURES",
        "holdSide": "long",
        "total": "0.1",
        "openPriceAvg": "3000",
        "margin": "30",
    }
    private = _FakeRest(payload={"data": [ex_item], "code": "00000"})

    class B:
        def publish(self, _stream: str, env: object) -> None:  # noqa: ANN401
            pl = getattr(env, "payload", None)
            d = pl if isinstance(pl, dict) else {}
            key = d.get("alert_key")
            if isinstance(key, str):
                repo.system_alerts.append(
                    (key, str(d.get("severity", "")), dict(d.get("details") or {}))
                )

    s = _settings_ghost(monkeypatch)
    res = run_position_drift_once(settings=s, repo=repo, private=private, bus=B())  # type: ignore[arg-type]
    assert res.get("ok") is True
    assert res.get("ghosts_repaired") == 1
    keys = {(r["inst_id"], r.get("hold_side"), r.get("product_type", "")) for r in repo.rows}
    assert ("ETHUSDT", "long", "USDT-FUTURES") in keys
    assert any(
        t[0] == "live-broker:GHOST_POSITION_DETECTED" for t in repo.system_alerts
    ), f"alerts={repo.system_alerts}"


def test_notional_mismatch_triggers_global_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published: list[bool] = []

    def _halt(url: str, active: bool) -> None:  # noqa: ARG001
        published.append(active)

    monkeypatch.setattr("live_broker.reconcile.position_drift.publish_global_halt_state", _halt)
    repo = InMemoryPosRepo()
    repo.rows.append(
        {
            "inst_id": "ETHUSDT",
            "product_type": "USDT-FUTURES",
            "hold_side": "long",
            "notional_value": "1",
            "raw_json": {"total": "0.1", "openPriceAvg": "3000"},
            "size_base": "0.1",
        }
    )
    ex = {
        "instId": "ETHUSDT",
        "productType": "USDT-FUTURES",
        "holdSide": "long",
        "total": "0.1",
        "openPriceAvg": "10000",
        "margin": "1000",
    }
    private = _FakeRest(payload={"data": [ex]})
    s = _settings_ghost(monkeypatch)
    s = s.model_copy(update={"live_broker_position_notional_halt_ratio": 0.01})
    run_position_drift_once(settings=s, repo=repo, private=private, bus=None)
    assert published and published[-1] is True
