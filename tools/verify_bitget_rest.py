#!/usr/bin/env python3
"""
Bitget-v2-REST Smoke/Verifikation (Prompt 6).

Profile:
  demo-read      — BITGET_DEMO_ENABLED=true, nur Lesepfade + Serverzeit
  demo-trade     — zusaetzlich eine Demo-Limit-Order (idempotent clientOid) + Cancel
  live-readonly  — BITGET_DEMO_ENABLED=false, nur Lesepfade

Voraussetzungen:
  LIVE_BROKER_ENABLED=true, DATABASE_URL/REDIS_URL wie live-broker,
  vollstaendiges Bitget-Kontext-ENV (BITGET_SYMBOL, MARKET_FAMILY, ggf. PRODUCT_TYPE).

demo-trade zusaetzlich:
  BITGET_CONFIRM_DEMO_TRADE=1  (explizite Zustimmung)

Keine Secrets in stdout (nur Statuscodes, classification, Pfade).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
_LB_SRC = REPO_ROOT / "services" / "live-broker" / "src"
_SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for p in (str(REPO_ROOT), str(_LB_SRC), str(_SHARED_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_settings():
    from config.bootstrap import bootstrap_from_settings
    from live_broker.config import LiveBrokerSettings

    s = LiveBrokerSettings()
    bootstrap_from_settings("live-broker", s)
    return s


def _summarize_probe(probe: dict[str, Any]) -> dict[str, Any]:
    snap = probe.get("market_snapshot")
    if isinstance(snap, dict):
        keys = ("symbol", "last_price", "mark_price", "request_time")
        snap = {k: snap.get(k) for k in keys}
    return {
        "public_api_ok": probe.get("public_api_ok"),
        "private_api_configured": probe.get("private_api_configured"),
        "private_auth_ok": probe.get("private_auth_ok"),
        "private_auth_classification": probe.get("private_auth_classification"),
        "credential_profile": probe.get("credential_profile"),
        "paptrading_header_active": probe.get("paptrading_header_active"),
        "credential_isolation_relaxed": probe.get("credential_isolation_relaxed"),
        "bitget_private_rest": probe.get("bitget_private_rest"),
        "market_snapshot": snap,
    }


def _safe(call: str, fn: Any) -> Any:
    try:
        return {"ok": True, "data": fn()}
    except Exception as exc:
        return {
            "ok": False,
            "step": call,
            "error": str(exc)[:300],
            "type": type(exc).__name__,
        }


def _run_reads(client: Any, _settings: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["server_time_sync"] = _safe(
        "sync_server_time",
        lambda: client.sync_server_time(force=True),
    )
    out["positions"] = _safe(
        "list_all_positions", lambda: client.list_all_positions().payload.get("data")
    )
    out["orders_pending"] = _safe(
        "list_orders_pending", lambda: client.list_orders_pending().payload.get("data")
    )
    now_ms = int(time.time() * 1000)

    def _hist() -> Any:
        return client.list_orders_history(
            params={
                "startTime": str(now_ms - 7 * 24 * 60 * 60 * 1000),
                "endTime": str(now_ms),
                "limit": "20",
            }
        ).payload.get("data")

    out["orders_history_sample"] = _safe("list_orders_history", _hist)
    return out


def _demo_trade_futures(client: Any, settings: Any) -> dict[str, Any]:
    if str(settings.market_family).lower() != "futures":
        raise SystemExit("demo-trade: aktuell nur futures (mix) unterstuetzt")
    if os.environ.get("BITGET_CONFIRM_DEMO_TRADE", "").strip() != "1":
        raise SystemExit(
            "demo-trade: BITGET_CONFIRM_DEMO_TRADE=1 setzen (echte Demo-Order)"
        )
    oid = f"vrfy-{uuid.uuid4().hex[:20]}"
    if len(oid) > 50:
        raise SystemExit("clientOid zu lang")
    body = {
        "symbol": settings.symbol,
        "productType": settings.product_type,
        "marginMode": str(settings.margin_account_mode or "isolated"),
        "marginCoin": settings.effective_margin_coin,
        "size": os.environ.get("BITGET_VERIFY_TRADE_SIZE", "0.001"),
        "side": "buy",
        "orderType": "limit",
        "price": os.environ.get("BITGET_VERIFY_TRADE_PRICE", "1"),
        "force": "gtc",
        "clientOid": oid,
        "reduceOnly": "NO",
    }
    placed = client.place_order(body)
    cancel_body = {
        "symbol": settings.symbol,
        "productType": settings.product_type,
        "marginCoin": settings.effective_margin_coin,
        "clientOid": oid,
    }
    canceled = client.cancel_order(cancel_body)
    return {
        "client_oid": oid,
        "place_code": placed.payload.get("code"),
        "cancel_code": canceled.payload.get("code"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Bitget REST Verifikation")
    ap.add_argument(
        "profile",
        choices=("demo-read", "demo-trade", "live-readonly"),
        help="Verifikationsprofil",
    )
    args = ap.parse_args()

    settings = _load_settings()
    if args.profile.startswith("demo") and not settings.bitget_demo_enabled:
        msg = "demo-* Profile erfordern BITGET_DEMO_ENABLED=true"
        print(json.dumps({"ok": False, "error": msg}, indent=2))
        return 2
    if args.profile == "live-readonly" and settings.bitget_demo_enabled:
        msg = "live-readonly erfordert BITGET_DEMO_ENABLED=false"
        print(json.dumps({"ok": False, "error": msg}, indent=2))
        return 2

    if not settings.live_broker_enabled:
        err = "LIVE_BROKER_ENABLED=true erforderlich (BitgetPrivateRestClient)"
        print(json.dumps({"ok": False, "error": err}, indent=2))
        return 2

    from live_broker.exchange_client import BitgetExchangeClient
    from live_broker.private_rest import BitgetPrivateRestClient

    client = BitgetPrivateRestClient(settings)
    ex = BitgetExchangeClient(settings)

    try:
        probe = ex.probe_exchange(private_rest=client)
        reads = _run_reads(client, settings)
        trade: dict[str, Any] | None = None
        if args.profile == "demo-trade":
            trade = _demo_trade_futures(client, settings)
        print(
            json.dumps(
                {
                    "ok": True,
                    "profile": args.profile,
                    "probe": _summarize_probe(probe),
                    "reads": reads,
                    "trade": trade,
                },
                indent=2,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "profile": args.profile,
                    "error": str(exc)[:500],
                    "error_type": type(exc).__name__,
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
