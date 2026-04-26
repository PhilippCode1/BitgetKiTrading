# Reconcile & Idempotency Drill Guide

## Warum Idempotency kritisch ist

Ohne stabile Idempotency koennen Timeouts und Retries Doppelorders erzeugen. Das ist ein P0-Risiko fuer Echtgeld.

## Warum Timeout gefaehrlich ist

Ein Submit-Timeout ist kein Erfolg. Es bedeutet `unknown_submit_state` und erzwingt Reconcile, bevor neue Opening-Orders erlaubt sind.

## Duplicate ClientOid

Duplicate `clientOid` wird fail-closed behandelt: kein neuer Opening-Submit, stattdessen idempotente Aufloesung/Reconcile.

## Reconcile-Drill Ablauf

1. Dry-run mit synthetischen Fixtures.
2. Externe Staging-/Shadow-Evidence sammeln.
3. Blocker, Audit und Alerts pruefen.
4. Owner-Review dokumentieren.

## Noetige ENV

- `EXECUTION_MODE=shadow`
- `LIVE_TRADE_ENABLE=false`
- `LIVE_BLOCK_SUBMIT_ON_RECONCILE_FAIL=true`
- `LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH=true`

## Kommandos

```bash
python scripts/reconcile_idempotency_evidence_report.py --output-md reports/reconcile_idempotency_summary.md --output-json reports/reconcile_idempotency_summary.json
python scripts/reconcile_truth_drill.py --dry-run --output-md reports/reconcile_truth_drill.md --output-json reports/reconcile_truth_drill.json
```

## Reports

- `reports/reconcile_idempotency_summary.md`
- `reports/reconcile_idempotency_summary.json`
- `reports/reconcile_truth_drill.md`
- `reports/reconcile_truth_drill.json`

## Wann `order_idempotency` verified werden darf

Nur mit echtem Staging-/Shadow-Drill inkl. Exchange-Truth, Duplicate/Timeout/DB-Failure-Nachweisen, Audit/Alert und Owner-Review.

## Wann `reconcile_safety` verified werden darf

Nur wenn Drift-/Unknown-/Stale-Szenarien runtime-seitig belegt blockieren und Safety-Latch/Operator-Flow extern nachgewiesen ist.

## Warum Live ohne Reconcile-Evidence NO_GO bleibt

Bei unklarer Order- oder Positionswahrheit drohen Phantomorders und Doppelrisiko. Deshalb bleibt `private_live_allowed=NO_GO`, bis Runtime-Evidence vorliegt.
