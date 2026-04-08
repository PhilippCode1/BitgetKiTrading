# api-gateway

## Purpose

Zentrale **HTTP**-Schnittstelle fuer das Dashboard und konsolidierte **Leseschicht** auf Postgres/Proxies. Sensible `/v1/*`-Bereiche sind mit **JWT (HS256)** und/oder **internem API-Key** absicherbar; Details: `docs/api_gateway_security.md`.

## Responsibilities

- `/health`, `/ready`, aggregierte System-Gesundheit (`/v1/system/health`).
- Proxies und DB-Reads: Paper, News, Signale, Registry, Learning (inkl. Backtest-Router), Monitor, Alerts, Live-Broker-Ops.
- Admin-API unter `/v1/admin` (Regeln, Strategie-Status) mit separaten Admin-Read/Write-Checks.
- Eventbus-Debug (`/events/*`) und DB-Schema-Checks wo eingebunden — mit **sensitive auth**, wenn erzwungen.
- **CORS**, **Redis-Rate-Limits**, **Safety-Burst-Limits**, **Audit-Log**, **manuelle Aktions-Tokens** fuer Live-Broker-Safety und `operator_release`.

## Dependencies

- Postgres, Redis

## Security (Kurz)

- `GATEWAY_JWT_SECRET`, `GATEWAY_INTERNAL_API_KEY`, `GATEWAY_ENFORCE_SENSITIVE_AUTH`, `GATEWAY_MANUAL_ACTION_*`, `PRODUCTION` — siehe `docs/api_gateway_security.md`.
- SSE `/v1/live/stream`: bei erzwungenem sensiblem Auth **Cookie** (`POST /v1/auth/sse-cookie`) oder Bearer/Internal-Key; keine offene Prod-Session ohne Mechanismus.

## Required ENV Keys (Auszug)

- `APP_ENV`, `APP_PORT`, `DATABASE_URL`, `REDIS_URL`, `LOG_LEVEL`
- Gateway-spezifisch: siehe `config/gateway_settings.py` und `.env.example`

## Weitere Doku

- `docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md` (Leser-Envelope, Beispiel-Payloads, Zahlungs-Modi)
- `docs/Deploy.md`, `docs/prod_runbook.md`, `docs/testing_guidelines.md`
