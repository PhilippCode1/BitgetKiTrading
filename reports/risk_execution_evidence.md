# Risk Execution Evidence Report

Status: synthetischer Fail-closed-Nachweis fuer Portfolio-Risk, Order-Idempotency und Reconcile-Safety.

## Summary

- Datum/Zeit: `2026-04-26T09:48:29.743600+00:00`
- Git SHA: `339dd15`
- Private-Live-Entscheidung: `NO_GO`
- Owner-Limits vorhanden: `False`
- Runtime-Evidence vorhanden: `False`
- Live erlaubt: `False`
- Status: `not_enough_evidence`
- Fehlende Required-Preflight-Blockgruende: `0`

## Live-Broker-Preflight-Coverage

- Abgedeckt: `idempotency_key_missing`, `portfolio_risk_not_safe`, `reconcile_not_ok`, `safety_latch_active`, `unknown_order_state_active`
- Fehlend: -

## Portfolio-Risk

- `missing_snapshot`: blockiert=`True`, Gruende=portfolio_snapshot_fehlt
- `stale_snapshot`: blockiert=`True`, Gruende=portfolio_snapshot_stale, owner_limits_fehlen
- `limit_breach`: blockiert=`True`, Gruende=correlation_stress_zu_hoch, total_exposure_ueber_limit, margin_usage_ueber_limit, max_concurrent_positions_ueberschritten, zu_viele_pending_live_candidates, net_long_exposure_ueber_limit, family_exposure_zu_hoch, owner_limits_fehlen

## Order-Idempotency

- `idempotency_missing`: state=`blocked`, Gruende=idempotency_fehlt
- `duplicate_client_oid`: state=`blocked`, Gruende=duplicate_client_order_id
- `unknown_submit_state_retry`: state=`blocked`, Gruende=unknown_submit_state_blockiert_neue_openings
- `timeout_sets_unknown`: state=`unknown_submit_state`, Gruende=submit_timeout_unknown_state
- `db_failure_requires_reconcile`: state=`reconcile_required`, Gruende=db_failure_reconcile_required
- `retry_without_reconcile`: state=`blocked`, Gruende=retry_ohne_reconcile_verboten

## Reconcile-Safety

- `stale`: status=`blocked`, Gruende=reconcile_stale
- `exchange_unreachable`: status=`blocked`, Gruende=exchange_unreachable
- `auth_failed`: status=`blocked`, Gruende=auth_failed
- `unknown_order_state`: status=`blocked`, Gruende=unknown_order_state
- `position_mismatch`: status=`blocked`, Gruende=position_mismatch
- `fill_mismatch`: status=`blocked`, Gruende=fill_mismatch
- `exchange_order_missing`: status=`warning`, Gruende=exchange_order_missing
- `local_order_missing`: status=`warning`, Gruende=local_order_missing
- `safety_latch_active`: status=`blocked`, Gruende=safety_latch_active

## Einordnung

- Synthetische Repo-Evidence ohne echte Orders und ohne Secrets.
- Portfolio-, Idempotency- und Reconcile-Fehler muessen vor Live-Submit denselben Live-Broker-Preflight blockieren.
- Externe Exchange-Truth-/Staging-Evidence bleibt fuer private Live erforderlich.
- Ohne Owner-Limits und Runtime-Evidence bleibt Status not_enough_evidence.
