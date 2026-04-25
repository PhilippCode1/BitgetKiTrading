# Secret- und API-Key-Matrix (Ueberblick)

**Maschinenlesbar:** [`config/required_secrets_matrix.json`](../config/required_secrets_matrix.json) — Spalten `local` / `staging` / `production` und `services` (`*` = alle Python-Services mit gemeinsamem Boot, sonst Liste z. B. nur `api-gateway`). **Staging** entspricht operativ typisch `APP_ENV=shadow` (Pre-Prod); die Spalten `staging` und `production` sind derzeit inhaltlich gleich, getrennt fuer spaetere Abweichungen.

**Umgebungs-Parität:** [`STAGING_PARITY.md`](../STAGING_PARITY.md) (Hostnamen, interne URLs, CORS, Smoke).

- Boot: [`config/required_secrets.py`](../config/required_secrets.py) `validate_required_secrets()` wird aus [`config/bootstrap.py`](../config/bootstrap.py) (`bootstrap_from_settings`) aufgerufen — klare `RequiredSecretsError`-Meldung bei leerem oder Platzhalter-ENV.
- CLI: [tools/validate_env_profile.py](../tools/validate_env_profile.py) (`python tools/validate_env_profile.py --env-file .env.local --profile local`) liest dieselbe Matrix (Union aller Keys fuer das Profil).

Gateway-Rollen / JWT-Claims: [`services/api-gateway/src/api_gateway/auth.py`](../services/api-gateway/src/api_gateway/auth.py).

## Oeffentlich (Browser / Build) vs. nur Server

| Kategorie                         | Beispiele                                                                           | Nie im Client-Bundle als Secret                                                                                                                                            |
| --------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Oeffentlich** (`NEXT_PUBLIC_*`) | `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL`, Feature-Flags ohne Secrets   | Enthalten nur unkritische URLs/Flags; trotzdem in Staging/Prod **explizit** setzen (Production-Build: kein stiller Localhost-Fallback in `apps/dashboard/src/lib/env.ts`). |
| **Nur Dashboard-Server**          | `API_GATEWAY_URL`, `DASHBOARD_GATEWAY_AUTHORIZATION`, `PAYMENT_MOCK_WEBHOOK_SECRET` | JWT und Webhook-Secrets bleiben in Server Components / Route Handlers (`server-env.ts`).                                                                                   |
| **Nur Gateway / Worker**          | `INTERNAL_API_KEY`, `GATEWAY_JWT_SECRET`, `OPENAI_API_KEY`, Bitget-Keys             | Niemals `NEXT_PUBLIC_*`; interne Aufrufe mit `X-Internal-Service-Key` wo vorgesehen.                                                                                       |

| Komponente          | ENV-Variable(n)                                                                                    | Verwendung                                                                     | Pflicht local (Paper)                                                                      | Pflicht STAGING (shadow) / PRODUCTION                                                              |
| ------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Postgres            | `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_DOCKER`                                         | DB-Verbindung Host + Compose                                                   | Ja                                                                                         | Ja                                                                                                 |
| Redis               | `REDIS_URL`, `REDIS_URL_DOCKER`                                                                    | Cache/Streams                                                                  | Ja                                                                                         | Ja                                                                                                 |
| Gateway JWT         | `GATEWAY_JWT_SECRET`, `GATEWAY_JWT_AUDIENCE`, `GATEWAY_JWT_ISSUER`                                 | HS256 fuer Dashboard/Clients                                                   | Ja                                                                                         | Ja                                                                                                 |
| Dashboard → Gateway | `DASHBOARD_GATEWAY_AUTHORIZATION`                                                                  | `Bearer <jwt>` Server-only (Next)                                              | Empfohlen (Console)                                                                        | Ja                                                                                                 |
| App JWT (legacy)    | `JWT_SECRET`                                                                                       | Einige interne Token                                                           | Ja                                                                                         | Ja                                                                                                 |
| Admin/UI            | `ADMIN_TOKEN`, `SECRET_KEY`, `ENCRYPTION_KEY`                                                      | Sessions, Verschluesselung                                                     | Ja                                                                                         | Ja                                                                                                 |
| Gateway Internal    | `GATEWAY_INTERNAL_API_KEY`, Header `X-Gateway-Internal-Key`                                        | Mutations/Admin am Gateway                                                     | Optional                                                                                   | Empfohlen                                                                                          |
| Service-to-Service  | `INTERNAL_API_KEY` (alias `SERVICE_INTERNAL_API_KEY` je Settings), Header `X-Internal-Service-Key` | Direktzugriff alert-engine, llm-orch, live-broker ops, monitor-engine `/ops/*` | Wenn Key gesetzt: Header noetig; in Prod ohne Key: **503** (`INTERNAL_AUTH_MISCONFIGURED`) | Key erforderlich; Routen-Inventar: [`docs/INTERNAL_SERVICE_ROUTES.md`](INTERNAL_SERVICE_ROUTES.md) |
| Bitget              | `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE` oder Demo-Varianten                 | Marktdaten/Trading                                                             | Optional (Demo)                                                                            | Live: Ja                                                                                           |
| LLM                 | `OPENAI_API_KEY`                                                                                   | News/LLM-Pfad                                                                  | Optional wenn Fake-Provider                                                                | Wenn kein Fake                                                                                     |
| Telegram            | `TELEGRAM_BOT_TOKEN`                                                                               | Alerts                                                                         | Optional                                                                                   | Wenn Outbox live                                                                                   |
| Stripe              | `STRIPE_*`                                                                                         | Commerce                                                                       | Optional                                                                                   | Wenn Zahlungen live                                                                                |

**Hinweis:** Es gibt keinen einzelnen „Master-API-Key“; Rollen sind getrennt (Gateway-JWT, Internal-Service, Exchange, Provider).

## Validierung

```powershell
python tools/validate_env_profile.py --env-file .env.local --profile local
python tools/validate_env_profile.py --env-file .env.shadow --profile staging
python tools/validate_env_profile.py --env-file .env.production --profile production
```

Bei Fehler: Exit-Code 1 und Liste fehlender oder Platzhalter-Variablen.

Vollstaendige Secret-Surface-Tabelle (Matrix + `NEXT_PUBLIC`-Allowlist + kritischer Zusatz): `python tools/inventory_secret_surfaces.py --report-md docs/production_10_10/07_secret_surface_inventory.md`.  
Production-Datei hart pruefen (keine Werte-Logs, nur redigierte Diagnose auf stderr): `python tools/verify_production_secret_sources.py --env-file <path> --strict --report-md /tmp/secret_source_report.md` — **erwartet FAIL** auf `.env.production.example` (Platzhalter-Template, kein gruenes „Production-Pass“).  
Zusatzregel: `NEXT_PUBLIC_*` mit Secret-ähnlichen Namen (`...SECRET`, `...TOKEN`, `...API_KEY`, `...JWT`) wird als **public leak risk** gewertet und failt in `--strict`.

## Leak, Rotation, Fail-Closed (Ablauf)

1. **Leak vermutet oder bestaetigt:** Live-Handel sofort begrenzen (Kill-Switch / `LIVE_TRADE_ENABLE=false` / `EXECUTION_MODE=shadow` laut Betriebsprozess), betroffene Dienste isolieren, kein Re-Commit von Rohtoken in Git/Tickets/Logs.
2. **Trennung nach Klasse:**  
   - **Bitget/Exchange:** neue API-Key-Tripel in Vault/SM, alte im Anbieter rotieren/verwerfen, `live-broker` / Gateway neu starten, Operator-Audit.  
   - **DB/Redis:** Zugangsdaten und `DATABASE_URL`/`REDIS_URL` aus Secret-Store, Verbindungsabbau erzwingen, Migrationen nur nach Freigabe.  
   - **JWT (`GATEWAY_JWT_SECRET`, `JWT_SECRET`, `DASHBOARD_GATEWAY_AUTHORIZATION`):** Secret rotieren, alle Session-/Bearer ableiten, Dashboard-Gateway-JWT neu minten.  
   - **Telegram/Provider:** `TELEGRAM_BOT_TOKEN`, Webhook-Secret, `OPENAI_API_KEY` getrennt rotieren; Webhooks im Bot-Provider neu setzen.  
   - **Zahlungen:** `STRIPE_*` bzw. Mock/Prod-Webhooks; Webhook-Endpoint-Geheimnisse im Gateway und Dashboard BFF.  
3. **Auditlog:** z. B. Gateway-Audit, Monitor-Alerts, Changelog mit Ticket/Owner; kein Secret im Klartext in Reports.  
4. **Evidenz:** Ampel **Secrets / Vault** im Gap-Register bleibt ohne reellen Vault-KMS-Drill **nicht** voll gruen (`docs/production_10_10/00_master_gap_register.md`).

## Staging-Smoke (Gateway + KI)

```bash
python scripts/staging_smoke.py --env-file .env.shadow
# optional: echte Staging-URL ohne Loopback erzwingen
python scripts/staging_smoke.py --env-file .env.shadow --disallow-loopback-gateway
```
