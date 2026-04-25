# Secrets Rotation Drill Report

- Generated at: `2026-04-25T12:16:17.571986+00:00`
- Mode: `simulated`
- Raw secret values included: `false`
- Inventory classes: `20`

## Simulated Findings

- Expired class: `JWT_SECRET` (`expired=true`)
- Compromised class: `TELEGRAM_BOT_TOKEN` (`reason=simulated_compromise_drill`)

## Rotation Plan

1. Freeze affected live-control path and confirm fail-closed state.
2. Create replacement credential in the environment-specific secret store.
3. Deploy secret reference version without printing raw values.
4. Restart dependent services in dependency order.
5. Run auth, health, reconcile, and operator-channel smoke checks.
6. Revoke old credential and record audit evidence.

## Service Restart Notes

- Restart gateway/auth clients after JWT and internal API key rotation.
- Restart live-broker only after exchange credentials and risk gates are verified.
- Restart alert-engine after Telegram credential rotation and webhook verification.

## Rollback

- Keep old credential disabled; rollback only to previous secret reference if not compromised.
- If compromise is suspected, rollback is service config only, never old credential reuse.
- Keep live trading blocked until owner signs the post-drill status.

## Go/No-Go

NO-GO for live money until real secret-store rotation evidence exists.
