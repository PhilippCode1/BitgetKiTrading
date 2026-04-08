#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${STACK_PROFILE:-local}"

if [[ $# -gt 0 ]]; then
  case "$1" in
    local|shadow|production)
      PROFILE="$1"
      shift
      ;;
  esac
fi

exec bash "$ROOT/scripts/bootstrap_stack.sh" "$PROFILE" "$@"
