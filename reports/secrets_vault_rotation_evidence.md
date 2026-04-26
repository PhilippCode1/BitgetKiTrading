# Secrets / Vault / Rotation Evidence Report

Status: repo-lokaler Nachweis fuer ENV-Templates, Secret-Surfaces und Rotation-Policies ohne echte Secrets.

## Summary

- Datum/Zeit: `2026-04-26T08:14:35.405980+00:00`
- Git SHA: `339dd15`
- Private Live: `NO_GO`
- Full Autonomous Live: `NO_GO`
- Failures: `1`
- External Required: `3`
- Browser-Public-Secret-Leaks: `6`
- Secret-Surface-Zeilen: `9471`
- Rotation-Policies: `20`

## ENV-Templates

| Datei | Profil | OK | Issues |
| --- | --- | --- | --- |
| `.env.local.example` | `local` | `True` | - |
| `.env.shadow.example` | `shadow` | `True` | - |
| `.env.production.example` | `production` | `True` | - |

## External Required

- `vault_runtime_secret_store_attestation_missing`
- `real_secret_rotation_drill_missing`
- `owner_signed_secret_rotation_acceptance_missing`

## Einordnung

- Repo-lokale Evidence ohne echte Secrets und ohne echte Vault-Zugriffe.
- Production-Templates duerfen Platzhalter enthalten, aber keine unsicheren Live-Defaults oder NEXT_PUBLIC-Secret-Namen.
- Private Live bleibt blockiert, bis echter Secret-Store, Rotation-Drill und Owner-Signoff extern belegt sind.
