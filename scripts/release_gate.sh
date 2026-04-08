#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
py="$(command -v python3 || command -v python)"
exec "$py" scripts/release_gate.py
