#!/usr/bin/env bash
# Full-Stack-Smoke: setzt voraus, dass `docker compose` (oder Stack-Skripte) bereits laufen.
# URLs wie in `scripts/healthcheck.sh` (API_GATEWAY_URL, MARKET_STREAM_URL, ...).
#
# Lokal typisch:
#   COMPOSE_ENV_FILE=.env.local docker compose -f docker-compose.yml \
#     -f docker-compose.local-publish.yml up -d
#   export API_GATEWAY_URL=http://localhost:8000
#   ... (alle *_URL aus healthcheck.sh)
#   bash scripts/integration_compose_smoke.sh
#
# Nicht fuer blinden CI-Push ohne laufenden Stack gedacht; optionaler workflow_dispatch-Job moeglich.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec bash scripts/healthcheck.sh
