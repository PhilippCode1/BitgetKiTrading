# Live Safety Drill Evidence Check

Status: prueft externen Kill-Switch-/Safety-Latch-/Emergency-Flatten-Nachweis ohne echte Secrets.

## Summary

- Schema: `live-safety-drill-evidence-v1`
- Environment: `staging`
- Execution Mode: `shadow`
- Git SHA: `missing`
- Operator: `missing`
- Reconcile nach Drill: `missing`
- Ergebnis: `FAIL`

## Blocker
- `drill_started_at_missing`
- `drill_completed_at_missing`
- `git_sha_missing`
- `operator_missing`
- `evidence_reference_missing`
- `kill_switch_arm_not_verified`
- `kill_switch_opening_submit_not_blocked`
- `kill_switch_release_not_operator_gated`
- `safety_latch_arm_not_verified`
- `safety_latch_submit_not_blocked`
- `safety_latch_replace_not_blocked`
- `safety_latch_release_reason_not_required`
- `emergency_flatten_not_tested`
- `emergency_flatten_not_reduce_only`
- `emergency_flatten_exchange_truth_not_checked`
- `emergency_flatten_no_increase_not_confirmed`
- `cancel_all_not_tested`
- `audit_trail_not_verified`
- `alert_delivery_not_verified`
- `main_console_state_not_verified`
- `reconcile_after_drill_not_ok`

## Warnings
- `owner_signoff_missing_external_required`

## Secret-Surface
- Keine unredigierten Secret-Felder erkannt.

## Einordnung

- Simulierte Drills sind Code-Evidence, aber keine Live-Freigabe.
- Live bleibt `NO_GO`, bis ein echter Staging-/Shadow-Drill mit Audit, Alert, Reconcile und Owner-Signoff vorliegt.
