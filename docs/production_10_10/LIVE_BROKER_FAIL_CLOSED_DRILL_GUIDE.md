# Live Broker Fail-Closed Drill Guide

## Ziel

Der Drill belegt, dass der Live-Broker bei Unsicherheit immer blockiert und niemals fail-open submittet.

## Szenarien

Getestet werden mindestens:

1. DB unavailable
2. Redis unavailable
3. Risk timeout
4. Market data stale
5. Orderbook missing
6. Exchange truth missing
7. Unknown instrument
8. Quarantined asset
9. Shadow mismatch
10. Operator release missing
11. Safety latch active
12. Kill switch active
13. Global halt active
14. Bitget auth error
15. Bitget permission error
16. Bitget timeout
17. Bitget 5xx
18. Duplicate clientOid
19. Reconcile degraded
20. ENV invalid

## Staging/Shadow Ablauf

- Nur `shadow`/`paper` Modus verwenden.
- Keine echten Live-Orders senden.
- Fail-Szenarien als kontrollierte Simulation oder Read-only Probe fahren.
- Audit und Alert-Pfade mitschreiben.

## Noetige ENV

- `EXECUTION_MODE=shadow`
- `LIVE_TRADE_ENABLE=false`
- `LIVE_BROKER_ENABLED=true`
- `LIVE_BLOCK_SUBMIT_ON_RECONCILE_FAIL=true`
- `LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH=true`
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true` (fuer Shadow-Gate-Drill)

## Kommandos

```bash
python tools/check_live_broker_preflight.py --strict --write-report reports/live_broker_preflight_matrix.md
python scripts/live_broker_fail_closed_evidence_report.py --output-md reports/live_broker_fail_closed_evidence.md --output-json reports/live_broker_fail_closed_evidence.json
python tools/check_live_broker_preflight.py --evidence-json docs/production_10_10/live_broker_fail_closed_evidence.template.json --strict --write-report reports/live_broker_fail_closed_evidence.md --output-json reports/live_broker_fail_closed_evidence.json
```

## Outputs

- `reports/live_broker_preflight_matrix.md`
- `reports/live_broker_fail_closed_evidence.md`
- `reports/live_broker_fail_closed_evidence.json`

## Wann `live_broker_fail_closed` auf verified darf

Nur mit echtem Staging-/Shadow-Drill, Runtime-Evidence, Git-SHA, Environment-Angabe, Audit- und Owner-Review.

## Warum ohne Drill weiter NO_GO

Ohne diesen Nachweis bleibt unbewiesen, dass Timeout/Provider-/Infra-Fehler sicher blockieren. Daher bleibt `private_live_allowed` zwingend `NO_GO`.
