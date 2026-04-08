#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROFILE="${1:-}"
if [[ -z "$PROFILE" ]]; then
  echo "Usage: bash scripts/bootstrap_stack.sh <local|shadow|production> [--with-observability] [--no-build] [--skip-migrations] [--wait-timeout <sec>]" >&2
  exit 1
fi
shift || true

WITH_OBSERVABILITY="${WITH_OBSERVABILITY:-false}"
BUILD_IMAGES="${BUILD_IMAGES:-true}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
WAIT_TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-300}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-2}"
BOOTSTRAP_POLL_MAX_SEC="${BOOTSTRAP_POLL_MAX_SEC:-10}"
BOOTSTRAP_DATASTORES="${BOOTSTRAP_DATASTORES:-auto}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-observability)
      WITH_OBSERVABILITY=true
      ;;
    --no-build)
      BUILD_IMAGES=false
      ;;
    --skip-migrations)
      RUN_MIGRATIONS=false
      ;;
    --wait-timeout)
      if [[ $# -lt 2 ]]; then
        echo "--wait-timeout erwartet Sekunden" >&2
        exit 1
      fi
      WAIT_TIMEOUT_SEC="$2"
      shift
      ;;
    *)
      echo "Unbekannte Option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

resolve_env_file() {
  case "$PROFILE" in
    local) echo ".env.local" ;;
    shadow) echo ".env.shadow" ;;
    production) echo ".env.production" ;;
    *)
      echo "Ungueltiges Profil: $PROFILE" >&2
      exit 1
      ;;
  esac
}

ENV_FILE="$(resolve_env_file)"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Fehlendes Profil: $ENV_FILE (Vorlage aus *.example anlegen und Secrets setzen)" >&2
  exit 1
fi

load_env_file() {
  local file="$1"
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line="${raw_line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" != *=* ]] && continue
    export "$line"
  done < "$file"
}

load_env_file "$ENV_FILE"

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Fehlendes Kommando: $name" >&2
    exit 1
  fi
}

resolve_python() {
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  echo "Kein Python-Interpreter gefunden (python/python3)." >&2
  exit 1
}

PYTHON_BIN="${PYTHON_BIN:-$(resolve_python)}"

# Gleiches Grundgeruest fuer alle Profile; Host-Ports fuer Engines nur bei local (und explizitem Override).
if [[ -z "${COMPOSE_FILES+x}" ]]; then
  case "$PROFILE" in
    local)
      COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.local-publish.yml)
      ;;
    shadow|production)
      COMPOSE_FILES=(-f docker-compose.yml)
      ;;
  esac
fi

require_command docker
require_command curl
require_command "$PYTHON_BIN"

if [[ -f tools/compose_start_preflight.py ]]; then
  echo "==> compose_start_preflight ($PROFILE)"
  "$PYTHON_BIN" tools/compose_start_preflight.py --env-file "$ENV_FILE" --profile "$PROFILE" || exit 1
fi

if [[ "$PROFILE" == "shadow" && -f scripts/mint_dashboard_gateway_jwt.py ]]; then
  echo "==> JWT fuer Dashboard->Gateway (Shadow: DASHBOARD_GATEWAY_AUTHORIZATION, Standard wie local)"
  echo "    Hinweis: Dashboard-Container nach .env.shadow-Aenderung neu erstellen (compose up --force-recreate dashboard)." >&2
  if ! "$PYTHON_BIN" scripts/mint_dashboard_gateway_jwt.py --env-file "$ENV_FILE" --update-env-file; then
    echo "mint_dashboard_gateway_jwt (shadow) fehlgeschlagen (PyJWT: pip install -r requirements-dev.txt)" >&2
    exit 1
  fi
fi

if [[ -f tools/validate_env_profile.py ]]; then
  echo "==> validate_env_profile ($PROFILE)"
  case "$PROFILE" in
    local) PY_PROF=local ;;
    shadow) PY_PROF=shadow ;;
    production) PY_PROF=production ;;
  esac
  "$PYTHON_BIN" tools/validate_env_profile.py --env-file "$ENV_FILE" --profile "$PY_PROF" || exit 1
fi

if [[ "$PROFILE" == "local" && -f scripts/mint_dashboard_gateway_jwt.py ]]; then
  echo "==> JWT fuer Dashboard->Gateway (DASHBOARD_GATEWAY_AUTHORIZATION)"
  if ! "$PYTHON_BIN" scripts/mint_dashboard_gateway_jwt.py --env-file "$ENV_FILE" --update-env-file; then
    echo "mint_dashboard_gateway_jwt fehlgeschlagen (PyJWT: pip install -r requirements-dev.txt)" >&2
    exit 1
  fi
fi

if [[ "$PROFILE" == "local" && -f tools/validate_env_profile.py ]]; then
  echo "==> validate_env_profile (local, nach Mint: DASHBOARD_GATEWAY_AUTHORIZATION)"
  "$PYTHON_BIN" tools/validate_env_profile.py --env-file "$ENV_FILE" --profile local --with-dashboard-operator || exit 1
fi

: "${DATABASE_URL:=}"
: "${REDIS_URL:=}"
: "${POSTGRES_DB:=bitget_ai}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_PASSWORD:=}"
if [[ -z "${DATABASE_URL_DOCKER}" && -n "${POSTGRES_PASSWORD}" ]]; then
  DATABASE_URL_DOCKER="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
fi
if [[ -z "${REDIS_URL_DOCKER}" ]]; then
  REDIS_URL_DOCKER="redis://redis:6379/0"
fi

compose() {
  COMPOSE_ENV_FILE="$ENV_FILE" \
  DATABASE_URL_DOCKER="$DATABASE_URL_DOCKER" \
  REDIS_URL_DOCKER="$REDIS_URL_DOCKER" \
  POSTGRES_DB="$POSTGRES_DB" \
  POSTGRES_USER="$POSTGRES_USER" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE" "$@"
}

detect_datastore_mode() {
  if [[ "$BOOTSTRAP_DATASTORES" != "auto" ]]; then
    echo "$BOOTSTRAP_DATASTORES"
    return
  fi
  if [[ "$DATABASE_URL_DOCKER" == *"@postgres:"* ]] || [[ "$REDIS_URL_DOCKER" == redis://redis:* ]]; then
    echo "compose"
  else
    echo "external"
  fi
}

DATASTORE_MODE="$(detect_datastore_mode)"

compose_tail_logs() {
  local svc="$1"
  echo "---- letzte Logs: $svc ----" >&2
  compose logs --tail 120 "$svc" 2>/dev/null || true
}

wait_for_service() {
  local service="$1"
  local deadline=$((SECONDS + WAIT_TIMEOUT_SEC))
  local cid=""
  local status=""
  local poll_n=0
  local sleep_sec

  while [[ $SECONDS -lt $deadline ]]; do
    cid="$(compose ps -q "$service" 2>/dev/null || true)"
    if [[ -n "$cid" ]]; then
      break
    fi
    poll_n=$((poll_n + 1))
    sleep_sec=$((POLL_INTERVAL_SEC + poll_n / 4))
    [[ $sleep_sec -gt $BOOTSTRAP_POLL_MAX_SEC ]] && sleep_sec=$BOOTSTRAP_POLL_MAX_SEC
    sleep "$sleep_sec"
  done

  if [[ -z "$cid" ]]; then
    echo "FAIL $service: kein Container-ID aus docker compose ps" >&2
    compose_tail_logs "$service"
    return 1
  fi

  poll_n=0
  while [[ $SECONDS -lt $deadline ]]; do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)"
    case "$status" in
      healthy|running)
        echo "OK  $service (docker state: $status)"
        return 0
        ;;
      unhealthy|exited|dead)
        echo "FAIL $service (docker state: $status)" >&2
        compose_tail_logs "$service"
        docker inspect "$cid" >/dev/null 2>&1 || true
        return 1
        ;;
    esac
    poll_n=$((poll_n + 1))
    sleep_sec=$((POLL_INTERVAL_SEC + poll_n / 3))
    [[ $sleep_sec -gt $BOOTSTRAP_POLL_MAX_SEC ]] && sleep_sec=$BOOTSTRAP_POLL_MAX_SEC
    sleep "$sleep_sec"
  done

  echo "FAIL $service (timeout waiting for healthy/running; letzter Status: ${status:-unknown})" >&2
  compose_tail_logs "$service"
  return 1
}

verify_external_datastores() {
  echo "==> Externe Datastores pruefen"
  DATABASE_URL="$DATABASE_URL" REDIS_URL="$REDIS_URL" "$PYTHON_BIN" - <<'PY'
import os
import psycopg
import redis

dsn = os.environ.get("DATABASE_URL", "").strip()
rurl = os.environ.get("REDIS_URL", "").strip()
if not dsn:
    raise SystemExit("DATABASE_URL fehlt fuer externen Datastore-Modus")
if not rurl:
    raise SystemExit("REDIS_URL fehlt fuer externen Datastore-Modus")

with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as conn:
    conn.execute("select 1")

client = redis.Redis.from_url(rurl, socket_connect_timeout=5, socket_timeout=5)
if not client.ping():
    raise SystemExit("Redis ping fehlgeschlagen")

print("external datastores ok")
PY
}

run_migrations() {
  if [[ "$RUN_MIGRATIONS" != "true" ]]; then
    echo "==> Migrationen uebersprungen (--skip-migrations)"
    return
  fi
  echo "==> Migrationen anwenden (kanonisch + optional demo-seeds)"
  DATABASE_URL="$DATABASE_URL" "$PYTHON_BIN" infra/migrate.py
  DATABASE_URL="$DATABASE_URL" "$PYTHON_BIN" infra/migrate.py --demo-seeds
}

build_application_images() {
  if [[ "$BUILD_IMAGES" != "true" ]]; then
    return
  fi
  echo "==> Baue Applikations-Images einmalig"
  compose build \
    market-stream \
    llm-orchestrator \
    feature-engine \
    structure-engine \
    news-engine \
    drawing-engine \
    signal-engine \
    paper-broker \
    live-broker \
    learning-engine \
    api-gateway \
    alert-engine \
    monitor-engine \
    dashboard
  BUILD_IMAGES=false
}

start_stage() {
  local label="$1"
  shift
  local services=("$@")
  local args=(up -d --no-deps)
  if [[ "$BUILD_IMAGES" == "true" ]]; then
    args+=(--build)
  fi

  echo "==> Stage: $label"
  echo "    Dienste: ${services[*]}"
  compose "${args[@]}" "${services[@]}"
  for service in "${services[@]}"; do
    wait_for_service "$service"
  done
}

start_observability() {
  if [[ "$WITH_OBSERVABILITY" != "true" ]]; then
    return
  fi
  echo "==> Stage: observability"
  compose --profile observability up -d --no-deps prometheus grafana
  wait_for_service prometheus
  wait_for_service grafana
}

echo "==> Bootstrap Profil=$PROFILE env=$ENV_FILE datastores=$DATASTORE_MODE build=$BUILD_IMAGES observability=$WITH_OBSERVABILITY"

if [[ "$DATASTORE_MODE" == "compose" ]]; then
  echo "==> Stage: datastores"
  compose up -d postgres redis
  wait_for_service postgres
  wait_for_service redis
else
  verify_external_datastores
fi

run_migrations
build_application_images
start_stage "1-kernfeeds" market-stream llm-orchestrator
start_stage "2-ableitende-engines" feature-engine structure-engine news-engine
start_stage "3-signale" drawing-engine signal-engine
start_stage "4-broker-live" paper-broker live-broker
start_stage "5-learning" learning-engine
start_stage "6-alert-vor-gateway" alert-engine
start_stage "7-gateway" api-gateway
start_stage "8-monitor" monitor-engine
start_observability
start_stage "dashboard" dashboard

echo "==> Finaler Smoke-Test"
if [[ "$PROFILE" == "shadow" || "$PROFILE" == "production" ]]; then
  export HEALTHCHECK_EDGE_ONLY=true
fi
bash "$ROOT/scripts/healthcheck.sh"

echo "==> Bootstrap erfolgreich abgeschlossen"
