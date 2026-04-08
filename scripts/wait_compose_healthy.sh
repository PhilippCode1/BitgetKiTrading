#!/usr/bin/env bash
# Wartet, bis `docker compose ps` keinen Container mehr als "unhealthy" zeigt.
# Repo-Root. COMPOSE_ENV_FILE (default .env.local), COMPOSE_FILE (default docker-compose.yml).
set -euo pipefail

: "${COMPOSE_WAIT_MAX_ROUNDS:=45}"
: "${COMPOSE_WAIT_SLEEP_SEC:=15}"
: "${COMPOSE_ENV_FILE:=.env.local}"
: "${COMPOSE_FILE:=docker-compose.yml}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker fehlt" >&2
  exit 2
fi

compose=(docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE")

round=0
while [[ $round -lt $COMPOSE_WAIT_MAX_ROUNDS ]]; do
  round=$((round + 1))
  out="$("${compose[@]}" ps 2>/dev/null || true)"
  if echo "$out" | grep -qi unhealthy; then
    echo "round $round/$COMPOSE_WAIT_MAX_ROUNDS: noch unhealthy, warte ${COMPOSE_WAIT_SLEEP_SEC}s..."
    sleep "$COMPOSE_WAIT_SLEEP_SEC"
    continue
  fi
  echo "wait_compose_healthy: kein 'unhealthy' in docker compose ps (Runde $round)"
  exit 0
done

echo "TIMEOUT — docker compose ps:" >&2
"${compose[@]}" ps || true
exit 1
