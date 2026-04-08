#!/usr/bin/env bash
# Build, Start, Health-Warten, Ports, optional xdg-open Dashboard.
# Repo-Root; COMPOSE_ENV_FILE (default .env.local), COMPOSE_FILE (default docker-compose.yml).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${COMPOSE_ENV_FILE:-.env.local}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
NO_BUILD="${NO_BUILD:-0}"
NO_OPEN="${NO_OPEN:-0}"
WAIT_TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-900}"
POLL_SEC="${POLL_SEC:-5}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env-Datei fehlt: $ENV_FILE" >&2
  exit 1
fi

export COMPOSE_ENV_FILE="$ENV_FILE"

args=(compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d)
if [[ "$NO_BUILD" != "1" ]]; then
  args+=(--build)
fi

echo "==> docker ${args[*]}"
docker "${args[@]}"

deadline=$(( $(date +%s) + WAIT_TIMEOUT_SEC ))
services=(
  postgres redis migrate market-stream llm-orchestrator
  feature-engine structure-engine news-engine drawing-engine signal-engine
  paper-broker live-broker learning-engine alert-engine api-gateway
  monitor-engine dashboard
)

echo "==> Warte auf healthy (max ${WAIT_TIMEOUT_SEC}s) ..."
while true; do
  now=$(date +%s)
  if (( now > deadline )); then
    echo "TIMEOUT" >&2
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps || true
    exit 1
  fi
  bad=()
  for s in "${services[@]}"; do
    if [[ "$s" == "migrate" ]]; then
      cid="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -a -q "$s" 2>/dev/null | head -1 || true)"
    else
      cid="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q "$s" 2>/dev/null | head -1 || true)"
    fi
    cid="$(echo -n "$cid" | tr -d '[:space:]')"
    if [[ -z "$cid" ]]; then
      bad+=("${s}:no-container")
      continue
    fi
    if [[ "$s" == "migrate" ]]; then
      st="$(docker inspect --format '{{.State.Status}}|{{.State.ExitCode}}' "$cid" 2>/dev/null || echo "?")"
      IFS='|' read -r a b <<<"$st"
      if [[ "$a" == "exited" && "$b" == "0" ]]; then
        continue
      fi
      if [[ "$a" == "created" || "$a" == "running" ]]; then
        bad+=("${s}:$a")
        continue
      fi
      if [[ "$a" == "exited" ]]; then
        bad+=("${s}:exit${b}")
        continue
      fi
      bad+=("${s}:$st")
      continue
    fi
    st="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo "?")"
    if [[ "$st" != "healthy" && "$st" != "running" ]]; then
      bad+=("${s}:$st")
    fi
  done
  if ((${#bad[@]} == 0)); then
    echo "==> Alle geprueften Dienste sind bereit."
    break
  fi
  echo "  noch offen: ${bad[*]}"
  sleep "$POLL_SEC"
done

echo ""
echo "==> Edge-Ports:"
echo "  API-Gateway   http://127.0.0.1:8000"
echo "  Dashboard     http://127.0.0.1:3000"
echo ""
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

if [[ "$NO_OPEN" != "1" ]]; then
  url="http://127.0.0.1:3000"
  echo ""
  echo "==> Oeffne Dashboard: $url"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" || true
  elif command -v open >/dev/null 2>&1; then
    open "$url" || true
  fi
fi

echo ""
echo "==> compose_up.sh fertig."
