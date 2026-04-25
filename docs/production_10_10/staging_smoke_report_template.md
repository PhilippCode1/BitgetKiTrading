# Staging Smoke Report Template

- Date/Time UTC:
- Git SHA:
- Release candidate:
- ENV file:
- APP_ENV:
- DEPLOY_ENV:
- Operator:
- Security reviewer:

## Redacted Runtime Values

- API_GATEWAY_URL:
- FRONTEND_URL:
- HEALTH_URL_DASHBOARD:
- HEALTH_URL_LIVE_BROKER:
- HEALTH_URL_LLM_ORCHESTRATOR:
- DATABASE_URL: `***REDACTED***`
- REDIS_URL: `***REDACTED***`
- DASHBOARD_GATEWAY_AUTHORIZATION: `***REDACTED***`

## Checks

| Check | Target | Status | Detail |
| --- | --- | --- | --- |
| gateway_health | | | |
| gateway_ready | | | |
| system_health | | | |
| dashboard_health | | | |
| live_broker_readiness | | | |
| llm_orchestrator_readiness | | | |
| bitget_read_only | | | |

## Live-Trade Status

- `LIVE_TRADE_ENABLE` must be `false`.
- `BITGET_WRITE_ENABLED` must be `false`.
- Any order-submit capability during staging is a production blocker.

## Secret Safety

- No raw secrets may appear in this report.
- Staging credentials must be scoped to staging and stored outside the repository.
- Customer exchange secrets must not be used in staging smoke reports.

## Go/No-Go Recommendation

- Recommendation:
- Blocking failures:
- External approvals:

## Next Steps

- Attach this report to the release candidate ticket.
- Resolve every failed check before production consideration.
- Repeat the smoke after any config, image, infra, or secret change.

## Signoff

- Release ticket:
- Operator:
- Security reviewer:
- Timestamp:
