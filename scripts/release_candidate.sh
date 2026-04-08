#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Kein Python-Interpreter gefunden: $PYTHON_BIN" >&2
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm fehlt im PATH" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker fehlt im PATH" >&2
  exit 1
fi

echo "==> Release-Candidate: Sanity / Security / Reproducibility"
"$PYTHON_BIN" tools/release_sanity_checks.py --strict

echo "==> Python Toolchain installieren"
"$PYTHON_BIN" -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -c constraints-runtime.txt -e ./shared/python
pip install -c constraints-runtime.txt -e ./services/feature-engine
pip install -c constraints-runtime.txt -e ./services/signal-engine
pip install -c constraints-runtime.txt -e ./services/paper-broker
pip install -c constraints-runtime.txt -e ./services/structure-engine
pip install -c constraints-runtime.txt -e ./services/drawing-engine
pip install -c constraints-runtime.txt -e ./services/learning-engine
pip install -c constraints-runtime.txt -e ./services/api-gateway
pip install -c constraints-runtime.txt -e ./services/monitor-engine
pip install -c constraints-runtime.txt -e ./services/news-engine
pip install -c constraints-runtime.txt -e ./services/market-stream
pip install -c constraints-runtime.txt -e ./services/llm-orchestrator
pip install -c constraints-runtime.txt -e ./services/alert-engine
pip install -c constraints-runtime.txt -e ./services/live-broker

echo "==> Python Tests / Coverage / Schema"
coverage erase
coverage run -m pytest tests shared/python/tests -m "not integration"
python tools/check_coverage_gates.py
python tools/check_schema.py --schema infra/tests/schemas/signals_recent_response.schema.json --json_file tests/fixtures/signals_fixture.json

echo "==> Security-Audits (blocking)"
python -m pip install pip-audit==2.7.3
pip-audit -r requirements-dev.txt

echo "==> Dashboard / Node"
pnpm install --frozen-lockfile
pnpm --dir apps/dashboard run lint
pnpm --dir apps/dashboard run test:ci
pnpm --dir apps/dashboard run build
pnpm audit --audit-level=high

echo "==> Docker / Compose / Migrations"
docker compose -f docker-compose.yml -f docker-compose.local-publish.yml config --quiet

if [[ -n "${DATABASE_URL:-}" ]]; then
  "$PYTHON_BIN" infra/migrate.py
else
  echo "DATABASE_URL nicht gesetzt — Migrationen im RC-Skript uebersprungen." >&2
fi

echo "==> Optionaler Compose-Smoke"
if [[ "${RUN_COMPOSE_SMOKE:-0}" == "1" ]]; then
  bash scripts/integration_compose_smoke.sh
fi

echo "==> Release-Candidate-Gates erfolgreich"
