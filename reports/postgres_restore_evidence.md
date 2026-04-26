# Postgres Restore / Disaster Recovery Evidence Check

Status: prueft externen Restore-/DR-Nachweis ohne echte Secrets.

## Summary

- Schema: `postgres-restore-dr-evidence-v1`
- Environment: `staging`
- Backup Label: `missing`
- Restore Status: `PENDING`
- Git SHA: `missing`
- RTO Sekunden: `None` / Budget `600`
- RPO Sekunden: `None` / Budget `300`
- Ergebnis: `FAIL`

## Blocker
- `backup_label_missing`
- `backup_storage_encryption_not_confirmed`
- `backup_artifact_sha256_missing`
- `restore_status_not_pass`
- `restore_target_missing`
- `git_sha_missing`
- `rto_seconds_missing`
- `rpo_seconds_missing`
- `checksum_not_verified`
- `migration_smoke_not_passed`
- `live_broker_read_smoke_not_passed`
- `reconcile_state_not_validated`
- `audit_trail_not_restored`
- `safety_latch_default_not_blocked`
- `alert_route_not_verified`
- `reviewer_missing`
- `reviewed_at_missing`
- `evidence_reference_missing`

## Warnings
- `owner_signoff_missing_external_required`

## Secret-Surface
- Keine unredigierten Secret-Felder erkannt.

## Einordnung

- Nur ein echter Staging-/Clone-Restore mit PASS, RTO/RPO und Review kann Live-Evidence sein.
- Dry-run, Template oder fehlende externe Referenz bleiben `NO_GO` fuer Live.
