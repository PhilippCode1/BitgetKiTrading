# Reconcile / Order-Idempotency Evidence Check

Status: prueft externen Reconcile-/Exchange-Truth-/Idempotency-Nachweis ohne echte Secrets.

## Summary

- Schema: `reconcile-idempotency-evidence-v1`
- Environment: `staging`
- Execution Mode: `shadow`
- Git SHA: `missing`
- Operator: `missing`
- Reconcile Status: `PENDING`
- Exchange Truth Source: `missing`
- Ergebnis: `FAIL`

## Blocker
- `drill_started_at_missing`
- `drill_completed_at_missing`
- `git_sha_missing`
- `operator_missing`
- `evidence_reference_missing`
- `exchange_truth_source_missing`
- `reconcile_status_not_ok`
- `reconcile_snapshot_not_fresh`
- `per_asset_reconcile_missing`
- `open_drift_present`
- `unknown_order_state_present`
- `position_mismatch_present`
- `fill_mismatch_present`
- `missing_exchange_ack_present`
- `retry_without_reconcile_not_blocked`
- `duplicate_client_oid_not_blocked`
- `idempotency_key_not_required`
- `timeout_unknown_state_not_set`
- `unknown_submit_state_not_blocking`
- `db_failure_reconcile_not_required`
- `safety_latch_not_armed_on_unresolved_duplicate`
- `audit_trail_not_verified`
- `alert_delivery_not_verified`
- `main_console_reconcile_state_not_verified`

## Warnings
- `owner_signoff_missing_external_required`

## Secret-Surface
- Keine unredigierten Secret-Felder erkannt.

## Einordnung

- Simulierte Reconcile-Drills sind Code-Evidence, aber keine Live-Freigabe.
- Live bleibt `NO_GO`, bis Exchange-Truth, Idempotency-Retry-Pfade, Audit, Alert und Owner-Signoff extern belegt sind.
