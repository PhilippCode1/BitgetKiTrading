# Admin / API-Gateway Security Evidence Report

Status: synthetischer Nachweis fuer Single-Owner-Admin, Gateway-Auth, Live-/Replay-/Admin-Gates und Audit.

## Summary

- Datum/Zeit: `2026-04-25T22:42:51.722874+00:00`
- Git SHA: `84d7b66`
- Private Live: `NO_GO`
- Full Autonomous Live: `NO_GO`
- Szenarien: `9`
- Fehlende Required-Szenarien: `0`
- Failures: `0`
- Audit valide: `9`
- Secret-safe: `True`

## Szenarien

| Szenario | Passed | Sensitive Aktion blockiert | Manual Action noetig | Private Live | Gruende |
| --- | --- | --- | --- | --- | --- |
| `missing_auth_blocks_admin` | `True` | `True` | `False` | `NO_GO` | `auth_missing_blocks_sensitive_action` |
| `single_admin_subject_mismatch_blocks` | `True` | `True` | `False` | `NO_GO` | `single_admin_subject_mismatch` |
| `legacy_admin_token_forbidden_in_production` | `True` | `True` | `False` | `NO_GO` | `legacy_admin_token_forbidden_in_production` |
| `read_role_cannot_mutate_live_broker` | `True` | `True` | `False` | `NO_GO` | `gateway_read_role_cannot_mutate_live_broker` |
| `operator_role_requires_manual_action_for_release` | `True` | `False` | `True` | `NO_GO` | `operator_release_requires_bound_manual_action_token` |
| `emergency_role_requires_manual_action_for_flatten` | `True` | `False` | `True` | `NO_GO` | `emergency_flatten_requires_bound_manual_action_token` |
| `customer_portal_cannot_admin` | `True` | `True` | `False` | `NO_GO` | `customer_portal_jwt_cannot_admin_or_live` |
| `public_secret_env_blocked` | `True` | `True` | `False` | `NO_GO` | `next_public_secret_name_blocked` |
| `auth_errors_are_redacted` | `True` | `False` | `False` | `NO_GO` | `auth_error_redaction_verified` |

## Einordnung

- Synthetische Repo-Evidence ohne echte Tokens, echte Secrets oder echte Live-Aktionen.
- Mutationsrollen allein sind keine Live-Freigabe; sensible Aktionen brauchen Owner-Kontext, Auth und gebundene Manual-Action-Evidence.
- Externe Owner-Signoff- und Runtime-Auth-Evidence bleibt fuer private Live erforderlich.
