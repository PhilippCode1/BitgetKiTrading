#!/usr/bin/env bash
# Go-Live-Vorabprüfung (ein Einstieg): Launch-Checklist mit ENV, Ops-Preflight, Vault.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-.env.production}"
STRICT=0
SKIP_AUDIT=0

for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --skip-audit) SKIP_AUDIT=1 ;;
  esac
done

if [[ "${GO_LIVE_CHECK_STRICT:-}" == "1" ]]; then
  STRICT=1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "WARN: Fehlt $ENV_FILE — Fallback auf .env.production.example" >&2
  ENV_FILE=".env.production.example"
fi

resolve_python() {
  if command -v python >/dev/null 2>&1; then echo python; return; fi
  if command -v python3 >/dev/null 2>&1; then echo python3; return; fi
  echo "Kein python im PATH." >&2
  exit 1
}

PY="$(resolve_python)"
ARGS=(--env-file "$ENV_FILE")
if [[ "$STRICT" == "1" ]]; then
  ARGS+=(--strict-runtime)
fi
if [[ "$SKIP_AUDIT" == "1" ]]; then
  ARGS+=(--skip-audit)
fi

echo "==> Go-Live Launch-Checklist"
exec "$PY" tools/go_live_launch_checklist.py "${ARGS[@]}"
