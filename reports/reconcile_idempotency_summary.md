# Reconcile / Order-Idempotency Evidence Report

Status: kombinierter repo-lokaler Nachweis fuer Reconcile-Safety und Order-Idempotency ohne echte Exchange-Orders.

## Summary

- Datum/Zeit: `2026-04-25T22:55:28.848443+00:00`
- Git SHA: `84d7b66`
- Private Live: `NO_GO`
- Full Autonomous Live: `NO_GO`
- Failures: `0`
- External Required: `5`
- External Template Status: `FAIL`
- External Template Blocker: `24`

## Live-Broker-Preflight-Coverage

- Abgedeckt: `idempotency_key_missing`, `portfolio_risk_not_safe`, `reconcile_not_ok`, `safety_latch_active`, `unknown_order_state_active`
- Fehlend: -

## Assertions

- Order-Idempotency fehlende Assertions: `0`
- Reconcile fehlende Assertions: `0`
- Secret-Surface-Issues: `0`
- Fehlende externe Pflichtblocker-Abdeckung: `0`

## External Required

- `real_exchange_truth_reconcile_drill_missing`
- `staging_duplicate_client_oid_drill_missing`
- `timeout_and_db_failure_reconcile_drill_missing`
- `audit_alert_main_console_reconcile_evidence_missing`
- `owner_signed_reconcile_idempotency_acceptance_missing`

## Einordnung

- Dieser Report kombiniert externe Template-Pruefung und synthetische Live-Preflight-Coverage.
- Ein PASS des Repo-Templates ohne echte Staging-/Shadow-Evidence waere ein Fehler.
- Private Live bleibt blockiert, bis Exchange-Truth, Retry-/Duplicate-Pfade, Audit, Alert und Owner-Signoff extern belegt sind.
