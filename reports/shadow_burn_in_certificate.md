# Shadow Burn-in Certificate Check

Status: prueft externen Shadow-Burn-in-Nachweis ohne echte Secrets.

## Summary

- Schema: `shadow-burn-in-certificate-v1`
- Environment: `shadow`
- Execution Mode: `shadow`
- Dauer Stunden: `None`
- Kalendertage: `0`
- Session-Cluster: `missing`
- Report Verdict: `PENDING`
- Report SHA256: `missing`
- Ergebnis: `FAIL`

## Blocker
- `started_at_missing`
- `ended_at_missing`
- `duration_hours_missing`
- `consecutive_calendar_days_less_than_14`
- `session_clusters_less_than_3`
- `stress_or_event_day_not_documented`
- `report_verdict_not_pass`
- `report_sha256_missing`
- `git_sha_missing`
- `runtime_env_snapshot_sha256_missing`
- `shadow_trade_enable_not_true`
- `live_broker_enabled_not_true`
- `require_shadow_match_before_live_not_true`
- `operator_release_required_not_true`
- `execution_binding_required_not_true`
- `max_leverage_missing`
- `symbols_observed_missing`
- `market_families_observed_missing`
- `playbook_families_observed_missing`
- `candidate_for_live_missing`
- `shadow_only_missing`
- `do_not_trade_missing`
- `audit_sample_not_reviewed`
- `forensics_sample_reference_missing`
- `reviewer_missing`
- `reviewed_at_missing`
- `evidence_reference_missing`

## Warnings
- `owner_signoff_missing_external_required`

## Secret-Surface
- Keine unredigierten Secret-Felder erkannt.

## Einordnung

- Fixture- oder Dry-run-PASS reicht nicht fuer private Live-Freigabe.
- Live bleibt `NO_GO`, bis ein echter Shadow-Burn-in mit 14 Tagen, Sessions, Report-SHA, Review und Owner-Signoff vorliegt.
