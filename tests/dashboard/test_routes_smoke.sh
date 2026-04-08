#!/usr/bin/env bash
set -euo pipefail
BASE="${API_BASE_URL:-http://localhost:8000}"

curl -sf "$BASE/v1/system/health" | head -c 400
echo

curl -sf "$BASE/v1/signals/recent?symbol=BTCUSDT&timeframe=1m&limit=3" | head -c 400
echo

curl -sf "$BASE/v1/news/scored?min_score=0&limit=3" | head -c 400
echo

curl -sf "$BASE/v1/paper/positions/open?symbol=BTCUSDT" | head -c 400
echo

curl -sf "$BASE/v1/paper/trades/recent?symbol=BTCUSDT&limit=5" | head -c 400
echo

curl -sf "$BASE/v1/paper/metrics/summary" | head -c 400
echo

curl -sf "$BASE/v1/paper/ledger/recent?limit=12" | head -c 400
echo

curl -sf "$BASE/v1/paper/journal/recent?symbol=BTCUSDT&limit=10" | head -c 400
echo

curl -sf "$BASE/v1/live-broker/runtime" | head -c 500
echo

curl -sf "$BASE/v1/live-broker/decisions/recent" | head -c 400
echo

curl -sf "$BASE/v1/live-broker/kill-switch/active" | head -c 500
echo

curl -sf "$BASE/v1/live-broker/audit/recent" | head -c 400
echo

curl -sf "$BASE/v1/live/state?symbol=BTCUSDT&timeframe=1m&limit=5" | head -c 500
echo

curl -sf "$BASE/v1/registry/strategies" | head -c 400
echo

curl -sf "$BASE/v1/learning/patterns/top" | head -c 400
echo

curl -sf "$BASE/v1/backtests/runs" | head -c 400
echo

curl -sf "$BASE/v1/admin/rules" | head -c 400
echo

echo "OK smoke"
