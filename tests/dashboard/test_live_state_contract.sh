#!/usr/bin/env bash
# Prompt 25: Smoke-Check Live-State JSON (api-gateway)
set -euo pipefail
BASE="${API_BASE_URL:-http://localhost:8000}"
URL="${BASE}/v1/live/state?symbol=BTCUSDT&timeframe=1m&limit=10"
echo "GET $URL"
json="$(curl -sf "$URL")"
python3 - <<'PY' <<<"$json"
import json, sys
d = json.load(sys.stdin)
assert d.get("symbol") == "BTCUSDT"
assert "timeframe" in d
assert "server_ts_ms" in d
assert isinstance(d.get("candles"), list)
assert "latest_signal" in d
assert isinstance(d.get("latest_drawings"), list)
assert isinstance(d.get("latest_news"), list)
assert "paper_state" in d
assert d["health"].get("db") in ("ok", "error")
for c in d["candles"]:
    assert "time_s" in c and "open" in c
print("live/state contract ok, candles=", len(d["candles"]))
PY
echo "OK"
