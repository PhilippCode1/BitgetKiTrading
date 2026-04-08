# URLs und Secrets für Operatoren (Single-Host / Compose)

## Öffentliche URLs (keine Secrets)

| Variable                   | Rolle                                                                              |
| -------------------------- | ---------------------------------------------------------------------------------- |
| `APP_BASE_URL`             | Kanonische HTTPS-URL des API-Gateways (Browser/Callbacks).                         |
| `FRONTEND_URL`             | HTTPS-URL des Dashboards.                                                          |
| `NEXT_PUBLIC_API_BASE_URL` | Gleiche API-Basis wie `APP_BASE_URL`, für **Next.js-Build** (Docker `build.args`). |
| `NEXT_PUBLIC_WS_BASE_URL`  | `wss://`-URL zum gleichen API-Host (SSE/WebSocket-Pfad wie im Gateway).            |
| `CORS_ALLOW_ORIGINS`       | Kommagetrennte **https**-Origins; muss `FRONTEND_URL` exakt abdecken.              |

`docker compose build` für das Dashboard liest `NEXT_PUBLIC_*` aus der gleichen `.env` wie `COMPOSE_ENV_FILE` — vor `docker compose build` setzen.

## Sicherheit am Edge

| Variable                          | Rolle                                                                      |
| --------------------------------- | -------------------------------------------------------------------------- |
| `GATEWAY_SEND_HSTS`               | Bei `PRODUCTION=true` und `APP_BASE_URL` mit **https** muss **true** sein. |
| `GATEWAY_SSE_COOKIE_SECURE`       | Bei TLS am Browser **true** (explizit oder implizit über Production).      |
| `GATEWAY_SSE_COOKIE_SAMESITE`     | `lax` (Standard) oder `strict`; `none` nur mit `Secure`.                   |
| `GATEWAY_CONTENT_SECURITY_POLICY` | Standard: restriktive JSON-API-CSP; leer = Header aus.                     |

## Secrets (niemals im Repo, niemals `NEXT_PUBLIC_*`, niemals Client-Logs)

- `POSTGRES_PASSWORD`, `DATABASE_URL` / `DATABASE_URL_DOCKER`
- `REDIS_URL` / `REDIS_URL_DOCKER`, ggf. `REDIS_PASSWORD`
- `INTERNAL_API_KEY`, `ADMIN_TOKEN`, `SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY`
- `GATEWAY_JWT_SECRET` und/oder `GATEWAY_INTERNAL_API_KEY` (jeweils ≥ 16 Zeichen bei erzwungenem sensiblen Auth)
- `BITGET_API_*`, Telegram, News/LLM-Keys nach Bedarf

Lieferung nur per Secret-Store oder sichere Laufzeit-ENV.

## Deploy-Check ohne Auth

`GET /v1/deploy/edge-readiness` — Checkliste (Forward-Header, HSTS-Flags, CORS-https), **ohne** Geheimnisse.

## Verweise

- `docs/env_profiles.md`, `docs/compose_runtime.md`, `docs/stack_readiness.md`
- `infra/reverse-proxy/README.md`
