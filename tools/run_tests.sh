#!/usr/bin/env bash
# Lokaler Testlauf (Prompt 29). Repo-Root als cwd.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="${PYTHONPATH:-}:$ROOT/shared/python/src"
export CI="${CI:-false}"

echo "[run_tests] ruff (unit/integration/check_schema)"
ruff check tests/unit tests/integration tools/check_schema.py

echo "[run_tests] black --check (unit/integration/tools)"
black --check tests/unit tests/integration tests/conftest.py tools/check_schema.py

echo "[run_tests] pytest (Marker integration ausgeschlossen)"
pytest -q tests shared/python/tests -m "not integration"

echo "[run_tests] coverage"
coverage erase
coverage run -m pytest tests shared/python/tests -m "not integration"
coverage report

if [[ "${RUN_INTEGRATION:-}" == "1" ]]; then
  echo "[run_tests] integration"
  pytest -q tests/integration -m integration
fi

if command -v pnpm >/dev/null 2>&1 && [[ -f apps/dashboard/package.json ]]; then
  echo "[run_tests] dashboard jest (ohne passWithNoTests — echte Suites erforderlich)"
  pnpm --dir apps/dashboard run test -- --runInBand
elif command -v npm >/dev/null 2>&1 && [[ -f apps/dashboard/package.json ]]; then
  echo "[run_tests] dashboard jest"
  (cd apps/dashboard && npm test -- --runInBand)
fi

echo "[run_tests] fertig"
