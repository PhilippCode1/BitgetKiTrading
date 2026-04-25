# ENV and Secrets Hardening

This document defines the fail-closed ENV rules for `bitget-btc-ai`. It is a
static safety layer for templates and runtime files. It does not replace Vault,
KMS, provider IAM, exchange-side permissions, or operator signoff.

## Profile Comparison

| Profile      | Purpose                                     | Fake provider         | Bitget demo | Localhost                     | Live order submit    |
| ------------ | ------------------------------------------- | --------------------- | ----------- | ----------------------------- | -------------------- |
| `local`      | Developer and paper-mode testing            | allowed               | allowed     | allowed                       | forbidden by default |
| `shadow`     | Production-like burn-in without real orders | forbidden for burn-in | forbidden   | forbidden in production paths | forbidden            |
| `production` | Real production runtime                     | forbidden             | forbidden   | forbidden                     | only with all gates  |

Local is explicitly not production-ready. Shadow may use production-like data,
but `LIVE_TRADE_ENABLE` must remain `false`.

## Hard Production Bans

When `PRODUCTION=true` or `APP_ENV=production`, these values are blocked by
`tools/check_env_10_10_safety.py`:

- `DEBUG=true`
- `LLM_USE_FAKE_PROVIDER=true`
- `NEWS_FIXTURE_MODE=true`
- `BITGET_DEMO_ENABLED=true`
- `BITGET_RELAX_CREDENTIAL_ISOLATION=true`
- localhost or loopback URLs in runtime values
- placeholder or blank runtime secrets in `--strict-runtime`
- secret-like `NEXT_PUBLIC_*` names or values
- demo and live Bitget credential sets mixed together

## Live-Trading Gates

If `LIVE_TRADE_ENABLE=true`, the checker requires:

- `EXECUTION_MODE=live`
- `LIVE_BROKER_ENABLED=true`
- `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`
- `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`
- `LIVE_REQUIRE_EXCHANGE_HEALTH=true`
- `RISK_HARD_GATING_ENABLED=true`
- `LIVE_KILL_SWITCH_ENABLED=true`
- `COMMERCIAL_ENABLED=true`
- `COMMERCIAL_ENTITLEMENT_ENFORCE=true`
- `COMMERCIAL_REQUIRE_CONTRACT_FOR_LIVE=true`
- explicit safety-latch or manual-action support

If any gate is missing, the profile is not valid for live money.

## Secret Name Semantics

| Name                              | Meaning                                                                                                      | Browser allowed? | Runtime only? | Secret Store required?           | Template value       |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------- | ------------- | -------------------------------- | -------------------- |
| `INTERNAL_API_KEY`                | Service-to-service key for `X-Internal-Service-Key`. Alias semantics may include `SERVICE_INTERNAL_API_KEY`. | no               | yes           | production/shadow yes            | placeholder only     |
| `SERVICE_INTERNAL_API_KEY`        | Service-specific alias for internal service auth.                                                            | no               | yes           | production/shadow yes            | placeholder only     |
| `GATEWAY_INTERNAL_API_KEY`        | Gateway-only `X-Gateway-Internal-Key`, not the same as `INTERNAL_API_KEY`.                                   | no               | yes           | production/shadow yes if enabled | blank or placeholder |
| `DASHBOARD_GATEWAY_AUTHORIZATION` | Server-side Next/BFF Authorization header for gateway calls.                                                 | no               | yes           | production/shadow yes            | `Bearer` placeholder |
| `JWT_SECRET`                      | App/session JWT signing secret.                                                                              | no               | yes           | yes                              | placeholder only     |
| `GATEWAY_JWT_SECRET`              | Gateway JWT signing secret.                                                                                  | no               | yes           | yes                              | placeholder only     |
| `ADMIN_TOKEN`                     | Legacy/break-glass admin token; must be short-lived and rotated.                                             | no               | yes           | yes                              | placeholder only     |
| `ENCRYPTION_KEY`                  | Field/envelope encryption control.                                                                           | no               | yes           | yes                              | placeholder only     |
| `BITGET_API_KEY`                  | Live Bitget API key reference.                                                                               | no               | yes           | yes                              | placeholder only     |
| `BITGET_API_SECRET`               | Live Bitget secret reference.                                                                                | no               | yes           | yes                              | placeholder only     |
| `BITGET_API_PASSPHRASE`           | Live Bitget passphrase reference.                                                                            | no               | yes           | yes                              | placeholder only     |
| `OPENAI_API_KEY`                  | LLM provider key.                                                                                            | no               | yes           | yes outside local fake mode      | placeholder only     |
| `TELEGRAM_BOT_TOKEN`              | Operator alert/command bot token.                                                                            | no               | yes           | yes for live channels            | placeholder only     |

`NEXT_PUBLIC_*` may contain public URLs and feature flags only. It must never
contain OpenAI, Bitget, Telegram bot, admin token, JWT, internal API key,
password, passphrase, encryption key, or Stripe secret material.

## Bitget Demo vs Live Keys

- `BITGET_DEMO_ENABLED=true` is local/test only.
- Demo and live Bitget credential names must not be populated together.
- Live credentials must be environment-scoped and must not be reused between
  shadow and production.
- Live order submit remains blocked until exchange health, operator release,
  shadow match, risk governor, commercial gates, kill-switch, and safety latch
  are all valid.

## Provider Keys

- `OPENAI_API_KEY` is required when fake-provider mode is disabled.
- `LLM_USE_FAKE_PROVIDER=true` is local/test only.
- `TELEGRAM_BOT_TOKEN` and webhook secrets are runtime-only and must rotate
  through the secret lifecycle policy.
- DB and Redis credentials must be secret-store backed in shadow/production.
  Redis or DB uncertainty must block trading paths, not degrade into live
  submit.

## Check Commands

```bash
python tools/check_env_10_10_safety.py --env-file .env.production.example --profile production --template
python tools/check_env_10_10_safety.py --env-file .env.shadow.example --profile shadow --template
python tools/check_env_10_10_safety.py --env-file .env.local.example --profile local --template
python tools/check_env_10_10_safety.py --env-file .env.production --profile production --strict-runtime
python tools/validate_env_profile.py --env-file .env.production.example --profile production
python tools/check_production_env_template_security.py
```

Template mode permits placeholders for server-side secrets. Runtime strict mode
does not.

## No-Go Examples

```env
PRODUCTION=true
DEBUG=true
```

```env
APP_ENV=production
LLM_USE_FAKE_PROVIDER=true
```

```env
APP_ENV=shadow
LIVE_TRADE_ENABLE=true
```

```env
NEXT_PUBLIC_OPENAI_API_KEY=...
```

```env
BITGET_DEMO_ENABLED=true
BITGET_API_KEY=...
```

## Secret Leak Procedure

1. Block live trading with kill-switch and `LIVE_TRADE_ENABLE=false`.
2. Revoke affected provider/exchange credentials.
3. Rotate through Vault/KMS or provider secret store.
4. Restart affected services in dependency order.
5. Run auth, readiness, Redis/DB, exchange-health, and reconcile checks.
6. Record evidence without raw secret values.

Rotation duties are defined in
`docs/production_10_10/secrets_rotation_and_credential_hygiene.md`.

## Production Evidence

Passing the static checker is `implemented` evidence. Production remains
blocked until runtime secrets are externally verified through Vault/KMS/provider
rotation evidence, Bitget key permissions, branch protection, alert delivery,
restore drills, and operator/legal signoff.
