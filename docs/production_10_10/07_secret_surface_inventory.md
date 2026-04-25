# Secret-Surface-Inventar (automatisch)

**Generiert:** `2026-04-25T10:10:04.700219+00:00`
**Quelle:** `config/required_secrets_matrix.json` + `apps/dashboard/public-env-allowlist.cjs` + Ergänzungen in `tools/inventory_secret_surfaces.py` (Bitget/Telegram/LLM).

**Anzahl Zeilen:** 21

## Tabelle

| ENV | Typ | Surface | Public im Browser? | Placeholder in Git-Template? | services | local | staging | production |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ADMIN_TOKEN` | secret | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `APEX_AUDIT_LEDGER_ED25519_SEED_HEX` | server_config | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | ["audit-ledger"] | optional | required | required |
| `API_GATEWAY_URL` | server_config | server_dashboard (Next server only) | no (server components / BFF) | no: use Vault/SM, never real values in template | * | required | required | required |
| `BITGET_API_KEY` | secret | server_backend | no | no: production-blocking if leaked | live-broker, market-stream, … | optional (Demo) | required (live data) | required for live |
| `BITGET_API_PASSPHRASE` | secret | server_backend | no | no: production-blocking if leaked | live-broker, … | optional (Demo) | required | required for live |
| `BITGET_API_SECRET` | secret | server_backend | no | no: production-blocking if leaked | live-broker, … | optional (Demo) | required | required for live |
| `DASHBOARD_GATEWAY_AUTHORIZATION` | server_config | server_dashboard (Next server only) | no (server components / BFF) | no: use Vault/SM, never real values in template | * | optional | required | required |
| `DATABASE_URL` | server_config | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `DATABASE_URL_DOCKER` | server_config | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `ENCRYPTION_KEY` | server_config | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `GATEWAY_JWT_SECRET` | secret | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | ["api-gateway"] | required | required | required |
| `INTERNAL_API_KEY` | secret | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `JWT_SECRET` | secret | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `NEXT_PUBLIC_API_BASE_URL` | public_config | browser_public | yes (flags/URLs, not secrets by design) | yes: URL/Flags as example only; must be non-loopback in prod | * | required | required | required |
| `NEXT_PUBLIC_WS_BASE_URL` | public_config | browser_public | yes (flags/URLs, not secrets by design) | yes: URL/Flags as example only; must be non-loopback in prod | * | required | required | required |
| `OPENAI_API_KEY` | secret | server_backend | no | no: production-blocking if leaked | llm-orchestrator, … | optional if fake | required if not fake | required if not fake |
| `POSTGRES_PASSWORD` | secret | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `REDIS_URL` | server_config | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `REDIS_URL_DOCKER` | server_config | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `SECRET_KEY` | secret | server_backend (Python/Workers) | no | no: use Vault/SM, never real values in template | * | required | required | required |
| `TELEGRAM_BOT_TOKEN` | secret | server_backend | no | no: production-blocking if leaked | alert path | optional | required if alerts live | required if outbox live |

## Hinweise

- `browser_public` inline’t nur unkritische Konfiguration; trotzdem in Prod bewusst setzen (kein stiller `localhost` im Production-Build).
- `server_dashboard` bleibt in `server-env.ts` / BFF, nie `NEXT_PUBLIC_*`.
- `server_backend` sind Exchange-Keys, interne API-Keys, DB-Passwörter — ausschließlich Laufzeit-Secret-Store, Rotation: `docs/SECRETS_MATRIX.md` (Abschnitt Rotation).

**Verifikation (Prod):** `python tools/verify_production_secret_sources.py --env-file <file> --strict`.
