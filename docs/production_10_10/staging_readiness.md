# Staging Readiness Contract

This document defines the mandatory staging contract for bitget-btc-ai release candidates.
No release may move directly from local development to production.

## Profile Decision

Staging is implemented as `APP_ENV=shadow` with `DEPLOY_ENV=staging`.

This is intentional. The current runtime type system already supports `shadow` and production-like
fail-closed gates. Adding a new `APP_ENV=staging` would widen runtime behavior before the release
gate is mature. `DEPLOY_ENV=staging` provides deployment identity while `EXECUTION_MODE=shadow`
keeps order submission blocked.

## Required Staging Rules

- `APP_ENV=shadow`
- `DEPLOY_ENV=staging`
- `PRODUCTION=true` for hardening checks, but no production datastore or customer data
- `EXECUTION_MODE=shadow`
- `LIVE_TRADE_ENABLE=false`
- `LIVE_BROKER_ENABLED=true` is allowed only for readiness and read paths
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`
- `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`
- `GATEWAY_ENFORCE_SENSITIVE_AUTH=true`
- `LLM_USE_FAKE_PROVIDER=false` for release-candidate smoke runs
- `NEWS_FIXTURE_MODE=false`
- `BITGET_DEMO_ENABLED=false`
- `BITGET_WRITE_ENABLED=false`
- no production database
- no production Redis
- no real customer secrets
- no browser-visible secrets

## Allowed Provider Use

Staging may use real provider read paths only when credentials are supplied through an external
secret store and scoped to staging. Bitget checks must be read-only and explicitly enabled with
`BITGET_READ_ONLY_CHECK_ENABLED=true`. No staging script in this repository submits exchange orders.

## Forbidden Conditions

- `LIVE_TRADE_ENABLE=true`
- `DEBUG=true`
- fake LLM or fixture news during release-candidate validation
- localhost URLs in strict runtime mode
- production-like database or Redis hosts
- placeholders or empty required secrets in strict runtime mode
- `NEXT_PUBLIC_*` secrets
- admin, exchange, OpenAI, Telegram, database, Redis, or gateway secrets in the browser

## Required Commands

Template check:

```bash
python tools/check_staging_profile.py --env-file .env.staging.example --template
```

Strict runtime check:

```bash
python tools/check_staging_profile.py --env-file .env.staging --strict-runtime
```

Dry-run smoke:

```bash
python scripts/staging_smoke.py --env-file .env.staging.example --dry-run
```

Runtime smoke with report:

```bash
python scripts/staging_smoke.py --env-file .env.staging --output-md reports/staging_smoke.md
```

## Production Blockers

Production remains blocked when any of these are true:

- no successful strict staging profile check exists
- no successful staging smoke report exists
- live trading is enabled in staging
- staging points at production DB or Redis
- staging uses real customer secrets or production customer data
- read-only provider checks are not clearly documented
- the release candidate ticket does not attach the generated smoke report

## External Setup Required

- dedicated staging Postgres instance
- dedicated staging Redis instance
- staging Gateway and Dashboard URLs behind real auth
- staging-scoped provider credentials in Vault or KMS-backed secret storage
- release ticket workflow that stores smoke reports and reviewer signoff

## Evidence

- Profile template: `.env.staging.example`
- Static checker: `tools/check_staging_profile.py`
- Smoke runner: `scripts/staging_smoke.py`
- Report template: `docs/production_10_10/staging_smoke_report_template.md`
- Tests: `tests/tools/test_check_staging_profile.py`
