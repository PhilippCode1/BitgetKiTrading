# Disaster Recovery Drill Report

- Datum/Zeit: `2026-04-26T10:08:32.755811+00:00`
- Git SHA: `339dd15`
- Status: `NOT_ENOUGH_EVIDENCE`
- Verified: `False`
- Evidence-Level: `synthetic`
- Private Live: `NO_GO`

## Szenarien

- `db_restart`: pass=`True`, actual=`block_or_reconcile_required`
- `redis_restart`: pass=`True`, actual=`block_or_reconcile_required`
- `live_broker_restart`: pass=`True`, actual=`block_or_reconcile_required`
- `api_gateway_restart`: pass=`True`, actual=`block_or_reconcile_required`
- `stale_event_stream`: pass=`True`, actual=`block_or_reconcile_required`
- `missing_local_order_after_restore`: pass=`True`, actual=`block_or_reconcile_required`
- `exchange_open_local_missing`: pass=`True`, actual=`block_or_reconcile_required`
- `local_open_exchange_missing`: pass=`True`, actual=`block_or_reconcile_required`
- `safety_latch_after_recovery`: pass=`True`, actual=`block_or_reconcile_required`
- `no_opening_until_reconcile_clean`: pass=`True`, actual=`block_or_reconcile_required`
- `audit_trail_after_restore`: pass=`True`, actual=`block_or_reconcile_required`
- `alert_after_recovery_issue`: pass=`True`, actual=`block_or_reconcile_required`

## External Required

- `staging_or_clone_drill_missing`
- `runtime_rto_rpo_measurement_missing`
- `owner_review_missing`
