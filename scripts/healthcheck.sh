#!/usr/bin/env bash
# Optional: vollstaendig wie pnpm rc:health mit Resilienz (Startup-Budget, 0/1) und/oder
#   HEALTHCHECK_STRESS_MODE=1  -> delegiert an rc_health_edge.py --stress
set -euo pipefail

_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${HEALTHCHECK_STRESS_MODE:=}"

if [[ "${HEALTHCHECK_STRESS_MODE}" == "1" || "${HEALTHCHECK_STRESS_MODE}" == "true" ]]; then
  if command -v python >/dev/null 2>&1; then
    _PY="python"
  elif command -v python3 >/dev/null 2>&1; then
    _PY="python3"
  else
    echo "FAIL healthcheck: python/python3 fehlt" >&2
    exit 1
  fi
  exec env PYTHONPATH="$_ROOT" "$_PY" "$_ROOT/scripts/rc_health_edge.py" --stress
fi

: "${API_GATEWAY_URL:=http://localhost:8000}"
: "${MARKET_STREAM_URL:=http://localhost:8010}"
: "${FEATURE_ENGINE_URL:=http://localhost:8020}"
: "${STRUCTURE_ENGINE_URL:=http://localhost:8030}"
: "${DRAWING_ENGINE_URL:=http://localhost:8040}"
: "${SIGNAL_ENGINE_URL:=http://localhost:8050}"
: "${NEWS_ENGINE_URL:=http://localhost:8060}"
: "${LLM_ORCH_URL:=http://localhost:8070}"
: "${PAPER_BROKER_URL:=http://localhost:8085}"
: "${LEARNING_ENGINE_URL:=http://localhost:8090}"
: "${ALERT_ENGINE_URL:=http://localhost:8100}"
: "${MONITOR_ENGINE_URL:=http://localhost:8110}"
: "${LIVE_BROKER_URL:=http://localhost:8120}"
: "${DASHBOARD_URL:=http://localhost:3000}"
: "${HEALTHCHECK_TIMEOUT_SEC:=5}"
# true: nur Gateway + Dashboard + aggregiertes /v1/system/health (Compose ohne local-publish Overlay).
: "${HEALTHCHECK_EDGE_ONLY:=false}"
: "${HEALTHCHECK_RETRY_ATTEMPTS:=4}"
: "${HEALTHCHECK_RETRY_BASE_SLEEP_SEC:=2}"

API_GATEWAY_SYSTEM_HEALTH_URL="${API_GATEWAY_SYSTEM_HEALTH_URL:-${API_GATEWAY_URL}/v1/system/health}"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "FAIL healthcheck: python/python3 fehlt" >&2
  exit 1
fi

with_retries() {
  local attempt=0
  local max="$HEALTHCHECK_RETRY_ATTEMPTS"
  while [[ $attempt -lt $max ]]; do
    if "$@"; then
      return 0
    fi
    attempt=$((attempt + 1))
    if [[ $attempt -lt $max ]]; then
      local w=$((HEALTHCHECK_RETRY_BASE_SLEEP_SEC * attempt))
      [[ $w -gt 20 ]] && w=20
      echo "RETRY in ${w}s ($attempt/$max): $*" >&2
      sleep "$w"
    fi
  done
  return 1
}

fetch_body() {
  local name="$1"
  local url="$2"
  local tmp_file
  local code

  tmp_file="$(mktemp)"
  if ! code="$(curl -sS -o "$tmp_file" -w "%{http_code}" --max-time "$HEALTHCHECK_TIMEOUT_SEC" "$url")"; then
    rm -f "$tmp_file"
    echo "FAIL $name ($url -> curl error)" >&2
    return 1
  fi
  if [[ "$code" != "200" ]]; then
    rm -f "$tmp_file"
    echo "FAIL $name ($url -> $code)" >&2
    return 1
  fi

  cat "$tmp_file"
  rm -f "$tmp_file"
}

check_ready_endpoint() {
  local name="$1"
  local url="$2"
  local body

  if ! body="$(fetch_body "$name" "$url")"; then
    return 1
  fi

  if printf '%s' "$body" | "$PYTHON_BIN" - "$name" <<'PY'
import json
import sys

name = sys.argv[1]
payload = json.load(sys.stdin)

if payload.get("ready") is not True:
    raise SystemExit(f"ready=false payload={payload}")

checks = payload.get("checks") or {}
failed = []
if isinstance(checks, dict):
    for key, value in checks.items():
        if isinstance(value, dict) and value.get("ok") is False:
            detail = str(value.get("detail", "failed"))[:200]
            failed.append(f"{key}: {detail}")
        elif isinstance(value, (list, tuple)) and value and not bool(value[0]):
            detail = value[1] if len(value) > 1 else "failed"
            failed.append(f"{key}:{detail}")

if failed:
    raise SystemExit("; ".join(failed))

print(f"OK  {name} ready")
PY
  then
    return 0
  fi

  echo "FAIL $name (ungueltiger ready payload von $url)" >&2
  return 1
}

check_status_endpoint() {
  local name="$1"
  local url="$2"
  local expected_service="$3"
  local body

  if ! body="$(fetch_body "$name" "$url")"; then
    return 1
  fi

  if printf '%s' "$body" | "$PYTHON_BIN" - "$name" "$expected_service" <<'PY'
import json
import sys

name = sys.argv[1]
expected_service = sys.argv[2]
payload = json.load(sys.stdin)
status = str(payload.get("status", "")).strip().lower()
service = str(payload.get("service", "")).strip().lower()

if status != "ok":
    raise SystemExit(f"status={status!r}")
if expected_service and service != expected_service:
    raise SystemExit(f"service={service!r}")

print(f"OK  {name} status=ok")
PY
  then
    return 0
  fi

  echo "FAIL $name (ungueltiger status payload von $url)" >&2
  return 1
}

check_gateway_system_health() {
  local body

  if ! body="$(fetch_body "api-gateway-system" "$API_GATEWAY_SYSTEM_HEALTH_URL")"; then
    return 1
  fi

  if printf '%s' "$body" | "$PYTHON_BIN" - <<'PY'
import json
import sys

payload = json.load(sys.stdin)

required = {
    "market-stream",
    "feature-engine",
    "structure-engine",
    "drawing-engine",
    "signal-engine",
    "news-engine",
    "llm-orchestrator",
    "paper-broker",
    "learning-engine",
    "alert-engine",
    "monitor-engine",
    "live-broker",
}

if payload.get("database") != "ok":
    raise SystemExit(f"database={payload.get('database')!r}")
if payload.get("redis") != "ok":
    raise SystemExit(f"redis={payload.get('redis')!r}")

services = {
    item.get("name"): item
    for item in payload.get("services", [])
    if isinstance(item, dict) and item.get("name")
}

missing = sorted(required - services.keys())
if missing:
    raise SystemExit(f"fehlende services={missing}")

bad = []
for name in sorted(required):
    status = str(services[name].get("status", "")).strip().lower()
    if status != "ok":
        bad.append(f"{name}:{status}")

if bad:
    raise SystemExit("; ".join(bad))

ops = payload.get("ops")
if not isinstance(ops, dict):
    raise SystemExit("ops summary fehlt")
for key in ("monitor", "alert_engine", "live_broker"):
    if not isinstance(ops.get(key), dict):
        raise SystemExit(f"ops.{key} fehlt")

warnings = payload.get("warnings") or []
warning_text = f" warnings={warnings}" if warnings else ""
monitor_open = int(ops["monitor"].get("open_alert_count") or 0)
outbox_failed = int(ops["alert_engine"].get("outbox_failed") or 0)
kill_switches = int(ops["live_broker"].get("active_kill_switch_count") or 0)
print(
    "OK  api-gateway-system database=ok redis=ok services=ok"
    f" monitor_open={monitor_open}"
    f" outbox_failed={outbox_failed}"
    f" active_kill_switches={kill_switches}"
    f"{warning_text}"
)
PY
  then
    return 0
  fi

  echo "FAIL api-gateway-system ($API_GATEWAY_SYSTEM_HEALTH_URL)" >&2
  return 1
}

fail=0

if [[ "${HEALTHCHECK_EDGE_ONLY}" == "true" ]]; then
  echo "==> Edge-only (keine direkten localhost-Checks auf interne Engines)"
  with_retries check_ready_endpoint "api-gateway" "${API_GATEWAY_URL}/ready" || fail=1
  echo "==> Dashboard Ready"
  with_retries check_status_endpoint "dashboard" "${DASHBOARD_URL}/api/health" "dashboard" || fail=1
  echo "==> Gateway Aggregate"
  with_retries check_gateway_system_health || fail=1
  exit "$fail"
fi

echo "==> Core Ready"
with_retries check_ready_endpoint "market-stream" "${MARKET_STREAM_URL}/ready" || fail=1
with_retries check_ready_endpoint "feature-engine" "${FEATURE_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "structure-engine" "${STRUCTURE_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "drawing-engine" "${DRAWING_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "signal-engine" "${SIGNAL_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "news-engine" "${NEWS_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "llm-orchestrator" "${LLM_ORCH_URL}/ready" || fail=1

echo "==> Broker Ready"
with_retries check_ready_endpoint "paper-broker" "${PAPER_BROKER_URL}/ready" || fail=1
with_retries check_ready_endpoint "learning-engine" "${LEARNING_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "live-broker" "${LIVE_BROKER_URL}/ready" || fail=1

echo "==> Edge/Ops Ready"
with_retries check_ready_endpoint "api-gateway" "${API_GATEWAY_URL}/ready" || fail=1
with_retries check_ready_endpoint "alert-engine" "${ALERT_ENGINE_URL}/ready" || fail=1
with_retries check_ready_endpoint "monitor-engine" "${MONITOR_ENGINE_URL}/ready" || fail=1

echo "==> Dashboard Ready"
with_retries check_status_endpoint "dashboard" "${DASHBOARD_URL}/api/health" "dashboard" || fail=1

echo "==> Gateway Aggregate"
with_retries check_gateway_system_health || fail=1

exit "$fail"
