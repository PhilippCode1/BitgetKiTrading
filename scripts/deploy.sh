#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

: "${DEPLOY_ENV:=production}"
: "${GIT_REPO:=<SET_ME>}"
: "${RUN_RELEASE_SANITY:=true}"

case "$DEPLOY_ENV" in
  local|shadow|production) ;;
  *)
    echo "DEPLOY_ENV muss local, shadow oder production sein (aktuell: $DEPLOY_ENV)" >&2
    exit 1
    ;;
esac

echo "==> Deploy-Start (DEPLOY_ENV=$DEPLOY_ENV)"
echo "    Secrets muessen bereits ueber Vault/KMS/Secret-Store in $ROOT/.env.$DEPLOY_ENV vorliegen."
echo "    Repo-Remote/Registry: $GIT_REPO"

if [[ "$DEPLOY_ENV" == "production" && "$GIT_REPO" == *"<SET_ME>"* ]]; then
  echo "GIT_REPO darf im Produktionsprofil kein Platzhalter bleiben." >&2
  exit 1
fi

if [[ "$RUN_RELEASE_SANITY" == "true" ]]; then
  echo "==> Release-Sanity (strict)"
  python "$ROOT/tools/release_sanity_checks.py" --strict
fi

extra_args=("$@")
if [[ "${WITH_OBSERVABILITY:-false}" == "true" ]]; then
  extra_args=(--with-observability "${extra_args[@]}")
fi

exec bash "$ROOT/scripts/bootstrap_stack.sh" "$DEPLOY_ENV" "${extra_args[@]}"
