#!/usr/bin/env bash
# Release-Candidate: Stack neu starten und Edge-Health pruefen (Linux/macOS/Git Bash).
# Windows: pwsh scripts/dev_up.ps1 bzw. dev_reset_db.ps1, danach pwsh scripts/rc_health.ps1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${COMPOSE_ENV_FILE:-.env.local}"
COMPOSE_YML="${COMPOSE_YML:-docker-compose.yml}"
RESET_VOLUMES=0

usage() {
  echo "Usage: $0 [--reset-volumes|-v]" >&2
  echo "  --reset-volumes  docker compose down -v (leere DB)" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset-volumes|-v) RESET_VOLUMES=1; shift ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "FEHLT: $ENV_FILE (z. B. cp .env.local.example .env.local und Passwoerter setzen)" >&2
  exit 1
fi

if [[ "$RESET_VOLUMES" -eq 1 ]]; then
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_YML" down -v
else
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_YML" down
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_YML" up -d --build
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_YML" ps

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "python3/python fehlt." >&2
  exit 1
fi

: "${API_GATEWAY_URL:=http://127.0.0.1:8000}"
: "${DASHBOARD_URL:=http://127.0.0.1:3000}"
export API_GATEWAY_URL DASHBOARD_URL

echo "Warte auf Edge-Health (bis zu ~15 Min, rc_health_edge.py mit Retry) ..."
ok=0
for attempt in $(seq 1 90); do
  if "$PY" "$ROOT/scripts/rc_health_edge.py"; then
    ok=1
    break
  fi
  echo "RETRY $attempt/90 in 10s ..."
  sleep 10
done

if [[ "$ok" -ne 1 ]]; then
  echo "FEHLER: rc_health_edge nach allen Versuchen nicht gruen." >&2
  echo "Logs: docker compose --env-file $ENV_FILE -f $COMPOSE_YML logs --tail=80 api-gateway" >&2
  exit 1
fi
