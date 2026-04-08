#!/usr/bin/env bash
# Release-/Smoke-Gate (Linux/macOS/Git-Bash): gleicher Ablauf wie pnpm rc:health / rc_health.ps1
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${1:-.env.local}"
exec python3 "$ROOT/scripts/rc_health_runner.py" "$ENV_FILE"
