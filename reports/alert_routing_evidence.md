# Alert Routing Delivery Evidence Check

Status: prueft externen Alert-Zustellnachweis ohne echte Secrets.

## Summary

- Schema: `alert-routing-evidence-v1`
- Environment: `staging`
- Git SHA: `missing`
- Operator: `missing`
- Kanal: `missing`
- Ack-Latenz Sekunden: `None` / Budget `900`
- Ergebnis: `FAIL`

## Blocker
- `drill_started_at_missing`
- `drill_completed_at_missing`
- `git_sha_missing`
- `operator_missing`
- `evidence_reference_missing`
- `delivery_channel_missing`
- `delivery_proof_reference_missing`
- `p0_route_not_verified`
- `p1_route_not_verified`
- `kill_switch_alert_not_delivered`
- `reconcile_alert_not_delivered`
- `market_data_stale_alert_not_delivered`
- `gateway_auth_alert_not_delivered`
- `human_ack_missing`
- `dedupe_not_verified`
- `runbook_link_not_verified`
- `main_console_alert_state_not_verified`
- `alert_payload_secret_safety_not_verified`
- `ack_latency_seconds_missing`

## Warnings
- `owner_signoff_missing_external_required`

## Secret-Surface
- `secret_like_field_not_redacted:no_secret_in_alert_payload`

## Einordnung

- YAML-Strukturtests ersetzen keinen echten Zustellnachweis.
- Live bleibt `NO_GO`, bis P0/P1-Routen, menschliche Quittierung, Runbook-Link, Main-Console-State und Owner-Signoff extern belegt sind.
