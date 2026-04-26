# Live Safety Drill Guide

## Kill-Switch

Der Kill-Switch stoppt neue riskante Aktionen sofort. Bei aktivem Kill-Switch sind Opening-Orders blockiert.

## Safety-Latch

Der Safety-Latch blockiert kritische Mutationen (Submit/Replace), bis ein Operator mit dokumentiertem Grund bewusst freigibt.

## Emergency-Flatten

Emergency-Flatten ist nur fuer kontrollierte Risikoreduktion gedacht:

- nur reduce-only
- nur mit sauberer Exchange-Truth
- kein Risikoanstieg erlaubt
- bei unklarer Position: fail-closed blockieren

## Warum Emergency-Flatten gefaehrlich ist

Fehlende Exchange-Truth oder falsche Richtung kann Exposure erhoehen. Deshalb wird ohne saubere Wahrheit blockiert.

## Noetige ENV

- `EXECUTION_MODE=shadow`
- `LIVE_TRADE_ENABLE=false`
- `LIVE_BROKER_ENABLED=true`
- `LIVE_BLOCK_SUBMIT_ON_RECONCILE_FAIL=true`
- `LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH=true`

## Dry-run

```bash
python scripts/live_safety_drill.py --dry-run --output-md reports/live_safety_summary.md --output-json reports/live_safety_summary.json
python scripts/live_safety_evidence_report.py --output-md reports/live_safety_evidence.md --output-json reports/live_safety_evidence.json
```

## Staging-/Shadow-Drill

Externe Drill-Evidence gegen `docs/production_10_10/live_safety_drill.template.json` erfassen, inklusive Audit/Alert/Main-Console-Nachweisen.

## Reports

- `reports/live_safety_summary.md`
- `reports/live_safety_summary.json`
- `reports/live_safety_evidence.md`
- `reports/live_safety_evidence.json`

## Wann `kill_switch_safety_latch` verified werden darf

Nur mit echtem Staging-/Shadow-Drill, Runtime-Evidence, Git-SHA, Umgebung und Owner-Review.

## Wann `emergency_flatten` verified werden darf

Nur wenn reduce-only, Exchange-Truth-Checks, Idempotenz/no-op-Faelle und Audit-Pfade in echter Umgebung nachgewiesen sind.

## Warum ohne Safety-Drill NO_GO

Ohne echten Safety-Drill bleibt unbewiesen, dass das System im Incidentfall sicher stoppt. Deshalb bleibt `private_live_allowed=NO_GO`.
