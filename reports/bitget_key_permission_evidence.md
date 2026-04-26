# Bitget Key Permission Evidence Check

Status: prueft externe Permission-Evidence ohne echte Secrets.

## Summary

- Schema: `bitget-exchange-readiness-v1`
- Environment: `production`
- Account Mode: `live_candidate`
- Read Permission: `True`
- Trade Permission: `True`
- Withdrawal Permission: `False`
- IP-Allowlist: `False`
- Account-Schutz: `False`
- Ergebnis: `FAIL`

## Blocker
- `ip_allowlist_not_confirmed`
- `account_protection_not_confirmed`
- `instrument_scope_missing`
- `reviewer_missing`
- `reviewed_at_missing`
- `evidence_reference_missing`

## Warnings
- `owner_signoff_missing_external_required`

## Secret-Surface
- Keine unredigierten Secret-Felder erkannt.

## Einordnung

- `PASS_WITH_WARNINGS` oder `PASS` ersetzt keinen Owner-Go/No-Go-Signoff.
- Withdrawal-Rechte sind immer P0-Blocker.
- Echte API-Keys duerfen nicht in diesem JSON stehen.
