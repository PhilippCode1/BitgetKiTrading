#!/usr/bin/env python3
"""
Einfacher Smoke-Test gegen laufenden paper-broker (localhost:8085).
Setze PAPER_BROKER_URL falls abweichend.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get("PAPER_BROKER_URL", "http://127.0.0.1:8085").rstrip("/")

    def get(path: str) -> dict:
        req = urllib.request.Request(f"{base}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def post(path: str, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{base}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    try:
        print("health:", get("/health"))
        acc = post("/paper/accounts/bootstrap", {"initial_equity_usdt": "10000"})
        print("bootstrap:", acc)
        aid = acc["account_id"]
        post(
            "/paper/sim/market",
            {
                "ts_ms": 1710000000000,
                "best_bid": "60000",
                "best_ask": "60010",
                "last_price": "60005",
                "mark_price": "60006",
            },
        )
        op = post(
            "/paper/positions/open",
            {
                "account_id": aid,
                "symbol": "BTCUSDT",
                "side": "long",
                "qty_base": "0.01",
                "leverage": "10",
                "margin_mode": "isolated",
                "order_type": "market",
            },
        )
        print("open:", op)
        pid = op["position_id"]
        cl = post(
            f"/paper/positions/{pid}/close",
            {"qty_base": "0.005", "order_type": "market"},
        )
        print("close:", cl)
    except urllib.error.URLError as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
