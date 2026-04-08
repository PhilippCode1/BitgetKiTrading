# Staging-Parität und Umgebungsmodell

Dieses Dokument ordnet **lokal**, **Staging/Pre-Prod** (im Repo typisch `APP_ENV=shadow`, Datei `.env.shadow`) und **Produktion** (`APP_ENV=production`) ein. Ziel: dieselben **architektonischen Regeln**, unterschiedliche **Hosts und Secrets**, keine versteckten Localhost-Sonderwege in Zielumgebungen.

## Begriffe

| Begriff                | Typische Kennzeichen im Repo                                                                                                                                                                                                     |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lokal**              | `PRODUCTION=false`, `APP_ENV=local`, `.env.local` — `HEALTH_URL_*` oft `localhost` auf dem **Host**; Compose kann im Container andere Werte setzen.                                                                              |
| **Staging / Pre-Prod** | `PRODUCTION=true`, `APP_ENV=shadow`, `.env.shadow` — gleiche Secret-Pflicht wie Produktion (Matrix-Spalte `staging`); interne URLs **Docker-Dienstnamen** (`http://live-broker:8120`), öffentliche URLs **echte Hosts** oder LB. |
| **Produktion**         | `PRODUCTION=true`, `APP_ENV=production`, `.env.production` — Matrix-Spalte `production`; TLS (`https`/`wss`); kein Fake-LLM, keine Fixture-News laut `config/settings.py`.                                                       |

Es gibt **kein** separates `APP_ENV=staging` in den Typliteralen — operativ heißt „Staging“ hier **shadow mit eigener Infrastruktur**.

## Bewusste Unterschiede (nicht Widersprüche)

1. **Intern vs. extern:** Vom **Gateway-Container** aus müssen `HEALTH_URL_*`, `LLM_ORCH_BASE_URL`, Broker-Basis-URLs auf **Erreichbarkeit im Compose-Netz** zeigen (`http://llm-orchestrator:8070`, nicht `localhost`). In `.env.local` stehen oft Host-`localhost`-Zeilen — das ist nur gültig, wenn Compose diese Variablen **überschreibt** (prüfen mit `docker compose config` / Container-ENV).
2. **Dashboard Next.js:** Server-seitig (`API_GATEWAY_URL`) soll in Staging/Prod **explizit** gesetzt sein. **Kein** stiller Fallback auf `NEXT_PUBLIC_*` oder Loopback außerhalb `NODE_ENV=development|test` (siehe `apps/dashboard/src/lib/server-env.ts`). Browser-URLs kommen aus `NEXT_PUBLIC_*` (Build-Zeit).
3. **CORS:** `CORS_ALLOW_ORIGINS` am Gateway muss die **exakte** Browser-Origin des Dashboards enthalten (Schema + Host + Port). Shadow/Prod: keine `*`-Wildcard für Credentials-Modus.
4. **CSP (Dashboard):** Production-Build: `connect-src` enthält nur `self` plus die konfigurierten API-/WS-Origins — **keine** `localhost`-Wildcards (siehe `apps/dashboard/next.config.js`). Dev-Build behält Localhost-Patterns für lokale Ports.

## Risiken (offen ansprechen)

| Risiko                                                              | Mitigation                                                                                                                                 |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `.env.local`-`localhost` im Gateway-Container unüberschrieben       | Deploy-Checkliste: effektive `HEALTH_URL_*` im laufenden Container verifizieren.                                                           |
| `NEXT_PUBLIC_*` und `API_GATEWAY_URL` zeigen auf verschiedene Hosts | Einheitliche öffentliche API-Basis dokumentieren; Compose setzt `API_GATEWAY_URL=http://api-gateway:8000` serverseitig.                    |
| JWT/Internal-Keys im Browser                                        | `DASHBOARD_GATEWAY_AUTHORIZATION` nur Server-ENV; Admin-Mutationen über BFF (`NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true` in Prod empfohlen). |
| Staging nutzt noch `LLM_USE_FAKE_PROVIDER`                          | In Shadow/Prod von pydantic/settings abgelehnt — dennoch Deploy-Review.                                                                    |

## Verifikation

### Pflicht-ENV (gleiche Maschinenlogik wie Boot)

```bash
python tools/validate_env_profile.py --env-file .env.shadow --profile staging
python tools/validate_env_profile.py --env-file .env.production --profile production
```

`staging` und `shadow` prüfen dieselbe Matrix-Spalte `staging` (heute inhaltlich identisch mit `production`).

### Staging-Smoke (Gateway + System-Health + KI-Pfad)

```bash
python scripts/staging_smoke.py --env-file .env.shadow
```

Optional strikt ohne Loopback-Gateway-URL:

```bash
python scripts/staging_smoke.py --env-file .env.shadow --disallow-loopback-gateway
```

### Weitere bestehende Werkzeuge

- `python scripts/api_integration_smoke.py --env-file .env.local` — lokal / Host-zentriert, mit Hinweis bei `localhost` in `HEALTH_URL_*`.
- `python scripts/verify_ai_operator_explain.py --env-file … --mode gateway` — nur KI-Pfad über Gateway.

## Organisatorisch / infrastrukturell (nicht im Repo ersetzbar)

- TLS-Zertifikate, DNS, WAF, Secret-Store (Vault/KMS) und Rotation.
- Echte Bitget-/Stripe-/OpenAI-Konten und rechtliche Freigaben für Live-Trading.
- Backups, Monitoring-Alerts und Incident-Runbooks außerhalb dieses Repos.

Siehe auch: `docs/SECRETS_MATRIX.md`, `config/required_secrets_matrix.json`, `docs/env_profiles.md`, `docs/operator_urls_and_secrets.md`, `AI_FLOW.md`.
