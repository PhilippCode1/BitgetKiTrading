#!/usr/bin/env bash
# Release-/Smoke-Gate (Linux/macOS/Git-Bash): gleicher Ablauf wie pnpm rc:health / rc_health.ps1
#   ./scripts/rc_health.sh [.env-Datei] [--stress]   (zusaetzliche Args wie rc_health_runner)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec python3 "$ROOT/scripts/rc_health_runner.py" "$@"
