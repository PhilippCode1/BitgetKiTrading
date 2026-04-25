# Secrets Rotation and Credential Hygiene

This document defines the secret lifecycle policy for `bitget-btc-ai`. It is a
production-readiness control, not a credential store. Never place raw secret
values, API keys, tokens, passwords, customer credentials, wallet data, or
provider credentials in this file.

## Principles

- Secrets are environment-scoped: local, shadow, and production must not reuse
  the same value.
- Production secrets live in a secret store such as Vault, KMS-backed platform
  secrets, or a managed provider secret reference.
- Rotation must be tested before live money is enabled.
- Compromise response must revoke the old credential first when reuse would be
  unsafe.
- Any uncertain credential is treated as sensitive and fail-closed.
- Customer exchange credentials must be represented only as tenant-scoped secret
  references, never as raw values in the browser, logs, repo, or analytics.

## Secret Classes

| Secret class                        | Owner                                  | Environment               | Sensitivity | Rotation frequency | Expiry expected?                  | Emergency revoke process                                                  | Where stored                                             | Where never stored                                      | Production live impact                                                        | Rotation test requirement                                          |
| ----------------------------------- | -------------------------------------- | ------------------------- | ----------- | ------------------ | --------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `BITGET_API_KEY`                    | Trading Operations / Security          | shadow, production        | critical    | 30 days            | yes                               | Disable key in Bitget, revoke IP allowlist entry, latch live broker.      | Vault/KMS-backed secret store per environment.           | Repo, browser, logs, dashboard payloads, test fixtures. | Live trading must block until replacement key is verified read-only first.    | Simulated drill plus demo/read-only exchange verification.         |
| `BITGET_API_SECRET`                 | Trading Operations / Security          | shadow, production        | critical    | 30 days            | yes                               | Revoke exchange credential pair and invalidate dependent broker sessions. | Vault/KMS-backed secret store per environment.           | Repo, browser, logs, dashboard payloads, test fixtures. | Order submission remains blocked until broker health and reconcile are clean. | Simulated drill plus broker restart and reconcile smoke.           |
| `BITGET_API_PASSPHRASE`             | Trading Operations / Security          | shadow, production        | critical    | 30 days            | yes                               | Rotate with Bitget keypair and invalidate old passphrase immediately.     | Vault/KMS-backed secret store per environment.           | Repo, browser, logs, dashboard payloads, test fixtures. | Live broker must fail closed until full credential set matches.               | Simulated drill plus credential-set consistency check.             |
| `OPENAI_API_KEY`                    | AI Platform / Security                 | local, shadow, production | high        | 60 days            | yes                               | Revoke provider key, pause LLM-dependent workflows, deploy replacement.   | Secret store or local developer vault; never committed.  | Repo, browser, logs, prompts, evaluation artifacts.     | LLM degradation is allowed; trading execution must not become less safe.      | Simulated provider-key rotation and fail-closed LLM fallback test. |
| `TELEGRAM_BOT_TOKEN`                | Operator Communications / Security     | shadow, production        | high        | 60 days            | yes                               | Revoke token via Telegram, disable webhook, rotate allowlist.             | Secret store per environment.                            | Repo, logs, screenshots, browser, chat transcripts.     | Operator commands must fail closed until channel is re-verified.              | Simulated token rotation and allowlist command test.               |
| `TELEGRAM_WEBHOOK_SECRET`           | Operator Communications / Security     | shadow, production        | high        | 60 days            | yes                               | Rotate webhook secret and reject old signatures.                          | Secret store per environment.                            | Repo, logs, browser, webhook responses.                 | Webhook ingestion must reject unsigned or stale requests.                     | Webhook signature rejection/acceptance test.                       |
| `JWT_SECRET`                        | Platform Security                      | local, shadow, production | critical    | 30 days            | yes                               | Rotate signing key, invalidate sessions, force token renewal.             | Secret store with key version metadata.                  | Repo, logs, browser storage as raw secret.              | Auth must fail closed for tokens signed by revoked keys.                      | Token invalidation and new-token acceptance test.                  |
| `GATEWAY_JWT_SECRET`                | Platform Security                      | local, shadow, production | critical    | 30 days            | yes                               | Rotate gateway signing key and reject old service tokens.                 | Secret store with per-environment key version.           | Repo, logs, browser storage as raw secret.              | Gateway must reject old tokens and surface safe 401/403 responses.            | Gateway auth negative/positive rotation test.                      |
| `INTERNAL_API_KEY`                  | Platform Security                      | local, shadow, production | high        | 45 days            | yes                               | Rotate internal key and restart dependent services in dependency order.   | Secret store per service and environment.                | Repo, logs, dashboard payloads.                         | Internal APIs must reject old keys and fail closed.                           | Service-to-service auth rotation smoke.                            |
| `GATEWAY_INTERNAL_API_KEY`          | Platform Security                      | local, shadow, production | high        | 45 days            | yes                               | Rotate gateway key and restart BFF/service clients.                       | Secret store per environment.                            | Repo, browser, logs, BFF JSON responses.                | Gateway and dashboard BFF must reject stale internal credentials.             | Gateway/BFF internal auth smoke.                                   |
| `ADMIN_TOKEN`                       | Platform Security / Operations         | local, shadow, production | critical    | 14 days            | yes                               | Revoke token, invalidate admin sessions, require operator re-approval.    | Short-lived secret store entry or break-glass vault.     | Repo, browser local storage, screenshots, logs.         | Admin actions must be unavailable until fresh authorization exists.           | Admin auth expiry and revoke test.                                 |
| `ENCRYPTION_KEY`                    | Platform Security                      | shadow, production        | critical    | 180 days           | yes                               | Execute envelope-key rotation and re-encrypt affected material.           | KMS/HSM/Vault transit, never as plain env in production. | Repo, logs, browser, database plaintext columns.        | Data decrypt/encrypt path must halt safely if key version is invalid.         | Envelope-key version drill in staging.                             |
| `DATABASE_URL`                      | SRE / Database Operations              | local, shadow, production | high        | 90 days            | yes                               | Rotate DB user/password, drain connections, verify migrations and health. | Secret store or platform-managed connection reference.   | Repo, logs, client-side bundles.                        | Services must fail readiness until DB auth is healthy.                        | DB credential rotation smoke and rollback plan.                    |
| `POSTGRES_PASSWORD`                 | SRE / Database Operations              | local, shadow, production | high        | 90 days            | yes                               | Rotate password, restart clients, revoke old role grants.                 | Secret store or managed database secret reference.       | Repo, logs, dashboard.                                  | Services must not submit orders without DB readiness.                         | DB password rotation and readiness test.                           |
| `REDIS_PASSWORD`                    | SRE / Platform Security                | local, shadow, production | high        | 90 days            | yes                               | Rotate Redis credential, restart clients, verify queues and latches.      | Secret store or managed Redis auth reference.            | Repo, logs, dashboard.                                  | Trading must block if Redis latch/state cannot be trusted.                    | Redis auth rotation and fail-closed latch test.                    |
| `PAYMENT_STRIPE_SECRET_KEY`         | Billing Operations / Security          | shadow, production        | critical    | 60 days            | yes                               | Revoke Stripe secret key, rotate webhook endpoints, pause billing writes. | Payment secret store entry per environment.              | Repo, browser, logs, customer portal payloads.          | Commercial gates must fail closed if billing truth is unavailable.            | Webhook/payment sandbox rotation test.                             |
| `PAYMENT_STRIPE_WEBHOOK_SECRET`     | Billing Operations / Security          | shadow, production        | high        | 60 days            | yes                               | Rotate webhook signing secret and reject old signatures.                  | Payment secret store entry per environment.              | Repo, logs, webhook responses.                          | Billing state must not update from unsigned/stale events.                     | Webhook signature rotation test.                                   |
| `VAULT_TOKEN`                       | SRE / Security                         | shadow, production        | critical    | 7 days             | yes                               | Revoke token, rotate child tokens, verify audit log and policies.         | Workload identity or short-lived platform secret mount.  | Repo, shell history, logs, CI output.                   | Services must fail closed if secret retrieval is untrusted.                   | Vault token renewal/revoke drill.                                  |
| `KMS_KEY_ID` or KMS reference       | SRE / Security                         | shadow, production        | high        | 365 days           | no, key versions rotate by policy | Disable compromised key version and re-point aliases after approval.      | KMS alias/reference in config, key material in KMS only. | Repo as key material, logs, browser.                    | Encrypted data path must block if key reference is invalid.                   | KMS alias/key-version staging drill.                               |
| Customer exchange secret references | Customer Security / Trading Operations | shadow, production        | critical    | 30 days            | yes                               | Revoke customer exchange credential reference and block tenant trading.   | Tenant-scoped secret store reference only.               | Browser, repo, logs, analytics, support screenshots.    | Affected tenant trading must block until customer re-authorization.           | Tenant-scoped reference rotation and cross-tenant leak test.       |

## Drill Commands

```bash
python scripts/secrets_rotation_drill.py --dry-run
python scripts/secrets_rotation_drill.py --mode simulated --output-md reports/secrets_rotation_drill.md
python tools/check_secret_lifecycle.py
python tools/check_secret_lifecycle.py --strict
```

The drill is static and safe. It simulates inventory, an expired secret class, a
compromised secret class, a rotation plan, service restart notes, rollback, and
a Go/No-Go statement. It must not contact providers or production systems.

## Production Evidence Requirement

Documentation, policy code, and simulated drills are `implemented` evidence.
Production can only move to `verified` for secret lifecycle after a real
secret-store rotation exercise proves:

- replacement secrets were created in the correct environment,
- old credentials were revoked,
- services restarted or reloaded safely,
- auth and readiness checks passed,
- no raw secret values were emitted to logs or reports,
- owner, environment, timestamp, reason, and rollback decision were recorded.

Until then, live money remains blocked by secret-lifecycle evidence.
