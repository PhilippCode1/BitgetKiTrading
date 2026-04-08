#!/usr/bin/env bash
set -euo pipefail
BASE="${API_BASE_URL:-http://localhost:8000}"

code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/admin/rules" \
  -H "Content-Type: application/json" \
  -d '{"rule_set_id":"default","rules_json":{"signal":{"min_strength_core":61}}}')"

if [[ "$code" != "401" ]]; then
  echo "expected HTTP 401 without admin token, got $code" >&2
  exit 1
fi
echo "OK admin unauth -> 401"
