# Secrets Rotation Report Template

Do not include raw secret values in this report.

## Metadata

- Date:
- Environment:
- Git SHA:
- Drill type: simulated / staging / production
- Owner:
- Approver:
- Incident ticket:

## Scope

| Secret class           | Environment | Owner    | Reason             | Rotation interval | Expired before drill? | Compromise suspected? |
| ---------------------- | ----------- | -------- | ------------------ | ----------------- | --------------------- | --------------------- |
| `EXAMPLE_SECRET_CLASS` | production  | Security | scheduled rotation | 30 days           | no                    | no                    |

## Actions

1. Confirmed affected services fail closed.
2. Created replacement secret in the environment-specific secret store.
3. Deployed new secret reference or version.
4. Restarted or reloaded dependent services.
5. Ran health, auth, reconcile, and alert checks.
6. Revoked old credential or disabled old key version.
7. Recorded audit payload.

## Evidence

- Secret store change reference:
- Service restart evidence:
- Healthcheck evidence:
- Auth negative/positive test evidence:
- Reconcile or fail-closed evidence:
- Alert delivery evidence:
- Logs reviewed for raw secret leakage:

## Results

- PASS / FAIL:
- Live money remained blocked during drill:
- Customer impact:
- Rollback used:
- Old credential reused: no

## Follow-up

- Open risks:
- Required owner action:
- Next rotation due:
- External signoff:
