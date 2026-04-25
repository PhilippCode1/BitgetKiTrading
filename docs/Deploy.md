# Deployment (Produktion V1)

**Launch-Freigabe, Cutover-Stufen und externe Blocker:** `docs/LAUNCH_DOSSIER.md`.

Produktionsnahe Deployments starten aus dem Profil `.env.production.example`. Lokale Entwicklung: `.env.local.example`, Shadow: `.env.shadow.example`, Tests: `.env.test.example`. **Profilvertrag, Pflicht-Secrets und Verbote:** `docs/env_profiles.md`. Geheimnisse nur zur Laufzeit aus **Vault**, **Secrets Manager** / **KMS** oder vergleichbar — keine festen Secrets im Repo.

## Voraussetzungen

- Docker & Docker Compose v3.9
- PostgreSQL 16+ und Redis 7 (oder die mit Compose gestarteten Container)
- Ausgefuehrte DB-Migrationen (siehe README → Migrationen)

## Wichtige ENV-Variablen (Kurzliste)

| Variable                                                                                                                                                              | Zweck                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PRODUCTION`                                                                                                                                                          | `true` aktiviert strengere Regeln (kein `DEBUG`, kein `LOG_LEVEL=DEBUG`).                                                                                                                                   |
| `APP_ENV`                                                                                                                                                             | z. B. `shadow`, `production`.                                                                                                                                                                               |
| `DEBUG`                                                                                                                                                               | Muss in Prod `false` sein (Validierung schlaegt sonst fehl).                                                                                                                                                |
| `DATABASE_URL`                                                                                                                                                        | Postgres-DSN (Passwort nur aus Secret Store).                                                                                                                                                               |
| `REDIS_URL`                                                                                                                                                           | Redis-URL.                                                                                                                                                                                                  |
| `DATABASE_URL_DOCKER`, `REDIS_URL_DOCKER`                                                                                                                             | Compose-interne DSNs fuer Container. Lokale Ops/Migrationen duerfen weiter `DATABASE_URL` / `REDIS_URL` mit Host-/localhost-Sicht verwenden.                                                                |
| `LOG_LEVEL`                                                                                                                                                           | `INFO` oder `WARNING` in Prod empfohlen.                                                                                                                                                                    |
| `LOG_FORMAT`                                                                                                                                                          | `json` fuer zentrale Logs; `plain` fuer lokale Lesbarkeit.                                                                                                                                                  |
| `VAULT_MODE`                                                                                                                                                          | `false` \| `none` \| `hashicorp` \| `aws` (Hinweis-Log in Prod bei `false`/`none`).                                                                                                                         |
| `VAULT_ADDR`, `VAULT_TOKEN` / `VAULT_ROLE_ID`+`VAULT_SECRET_ID`                                                                                                       | Beispiel Vault.                                                                                                                                                                                             |
| `KMS_KEY_ID`                                                                                                                                                          | Beispiel AWS KMS.                                                                                                                                                                                           |
| `DEPLOY_ENV`, `DEPLOY_SCRIPT`                                                                                                                                         | Metadaten fuer Deploy-Skripte.                                                                                                                                                                              |
| `ENABLE_DEBUG_METRICS`                                                                                                                                                | Feature-Flag fuer erweiterte Telemetrie.                                                                                                                                                                    |
| `EXECUTION_MODE`                                                                                                                                                      | Verbindlicher globaler Betriebsmodus: `paper`, `shadow`, `live`. Fuer das aktuelle Produktionsprofil bleibt `shadow` der sichere Default, bis ein echter Live-Trade-Gate freigegeben ist.                   |
| `STRATEGY_EXEC_MODE`                                                                                                                                                  | Strategy-/Automation-Release: `manual` oder `auto`.                                                                                                                                                         |
| `SHADOW_TRADE_ENABLE`, `LIVE_TRADE_ENABLE`                                                                                                                            | Harte Freigaben ueber dem globalen Mode. Shadow nutzt dieselbe Fachlogik wie Live, sendet aber niemals echte Orders; reale Orders sind nur mit `EXECUTION_MODE=live` und `LIVE_TRADE_ENABLE=true` moeglich. |
| —                                                                                                                                                                     | **Modusmatrix, Guard-Rails, Operator-Kommandos:** `docs/execution_modes.md`. Abgeleitete API-Sicht: `execution_runtime_snapshot` (Gateway `/v1/system/health` → `execution.execution_runtime`).             |
| `BITGET_UNIVERSE_MARKET_FAMILIES`, `BITGET_UNIVERSE_SYMBOLS`, `BITGET_WATCHLIST_SYMBOLS`, `FEATURE_SCOPE_SYMBOLS`, `FEATURE_SCOPE_TIMEFRAMES`, `SIGNAL_SCOPE_SYMBOLS` | universeller Instrument- und Analytics-Scope. Alle Profile nutzen dieselbe Kernlogik; die Profile unterscheiden sich nur in Gates und Secrets.                                                              |
| `LIVE_BROKER_PORT`, `LIVE_BROKER_ENABLED`, `LIVE_KILL_SWITCH_ENABLED`                                                                                                 | Live-Broker-Slot im Compose-Stack. Der aktuelle `live-broker`-Dienst ist die Exchange-/Control-Plane; echte Order-Sends bleiben zusaetzlich durch `LIVE_TRADE_ENABLE` gated.                                |
| `LIVE_ALLOWED_MARKET_FAMILIES`, `LIVE_ALLOWED_SYMBOLS`, `LIVE_ALLOWED_PRODUCT_TYPES`                                                                                  | Family-/Instrument-Whitelist fuer den Live-Broker. Futures pruefen zusaetzlich `productType`; Spot/Margin werden ueber `market_family` gegated.                                                             |
| `INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC`, `INSTRUMENT_CATALOG_CACHE_TTL_SEC`, `INSTRUMENT_CATALOG_MAX_STALE_SEC`                                                     | Refresh-, Cache- und Stale-Grenzen des zentralen Instrumentenkatalogs.                                                                                                                                      |
| `RISK_ALLOWED_LEVERAGE_MIN`, `RISK_ALLOWED_LEVERAGE_MAX`, `RISK_DEFAULT_ACTION`, `RISK_REQUIRE_7X_APPROVAL`, `RISK_HARD_GATING_ENABLED`                               | Risk-Gates; Leverage **7..75** (Minimum 7); ohne freigegebenen 7x-Fall bei aktivierter Policy → `do_not_trade`.                                                                                             |
| `BITGET_MARKET_FAMILY`, `BITGET_PRODUCT_TYPE`, `BITGET_MARGIN_ACCOUNT_MODE`, `BITGET_MARGIN_LOAN_TYPE`, `BITGET_DISCOVERY_SYMBOLS`, `BITGET_*_DEFAULT_*`              | aktiver Bitget-Instrumentkontext plus family-spezifische Defaults fuer Spot/Margin/Futures und Discovery-/Execution-Modus.                                                                                  |
| `MODEL_OPS_*`                                                                                                                                                         | Registry-, Approval-, Drift- und Rollback-Keys fuer Model-Ops / Shadow-Evaluation.                                                                                                                          |
| `API_AUTH_MODE`, `SECURITY_ALLOW_EVENT_DEBUG_ROUTES`, `SECURITY_ALLOW_DB_DEBUG_ROUTES`, `SECURITY_ALLOW_ALERT_REPLAY_ROUTES`, `INTERNAL_API_KEY`                      | Produktionsschutz fuer Edge-Auth, Replay/Debug und direkte interne Service-Aufrufe (`X-Internal-Service-Key`).                                                                                              |
| `HEALTH_URL_*`                                                                                                                                                        | Gateway-Aggregatpfade auf die `/ready`-Endpoints der internen Services; `GET /v1/system/health` materialisiert daraus zusaetzlich eine Ops-Sicht fuer Live-Broker, Monitor-Alerts und Alert-Outbox.         |
| `MONITOR_SERVICE_URLS`, `MONITOR_STREAMS`                                                                                                                             | Monitor-Engine-Vertrag fuer HTTP-Service-Checks und Stream-Lag. Fuer den integrierten Live-Broker-Pfad gehoert `events:system_alert` in die Streams.                                                        |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`                                                                                                                        | Grafana-Login bei Compose-Profil `observability` (nur Beispiel-Defaults in `docker-compose.yml`; in Prod setzen).                                                                                           |
| `THRESH_LIVE_RECONCILE_STALE_MS`, `THRESH_LIVE_ERROR_LOOKBACK_MS`, `THRESH_LIVE_KILL_SWITCH_AGE_MS`                                                                   | Live-Broker-spezifische Monitor-Schwellen fuer Reconcile-Lag, kritische Audit-Fehler und aktive Kill-Switches.                                                                                              |
| `FEATURE_MAX_EVENT_AGE_MS`, `SIGNAL_MAX_*_AGE_MS`, `LEARN_MAX_FEATURE_AGE_MS`                                                                                         | Prompt-13-Data-Quality-Gates fuer Candle-Inputs, as-of-Scoring und Learning-Snapshots; gemeinsam mit dem Shared-Feature-Schema-Hash verhindern sie stillen Train-/Infer-Drift.                              |
| `*_URL` im Script-Abschnitt                                                                                                                                           | Hostseitige Smoke-Targets fuer `scripts/healthcheck.sh` (z. B. `MARKET_STREAM_URL`, `LLM_ORCH_URL`, `LIVE_BROKER_URL`).                                                                                     |
| `CORS_ALLOW_ORIGINS`                                                                                                                                                  | API-Gateway: erlaubte Origins (komma-separiert).                                                                                                                                                            |
| `ADMIN_TOKEN`                                                                                                                                                         | Legacy-Admin-Header nur wenn sensibles Gateway-Auth **nicht** erzwungen ist (lokal); in Prod typisch JWT/`GATEWAY_INTERNAL_API_KEY`.                                                                        |
| `GATEWAY_JWT_SECRET`, `GATEWAY_INTERNAL_API_KEY`, `GATEWAY_ENFORCE_SENSITIVE_AUTH`, `GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN`                                                | Gateway-Auth fuer sensible Routen; siehe `docs/api_gateway_security.md`.                                                                                                                                    |
| `DASHBOARD_GATEWAY_AUTHORIZATION`, `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY`                                                                                               | Dashboard: serverseitiger Gateway-`Authorization`-Header; Proxy-Modus fuer Admin ohne Secrets im Browser (`docs/dashboard_operator.md`).                                                                    |

Vollstaendige Liste: `.env.example` (deduplizierter Key-Katalog, nur Platzhalter committen).

## Profilvorlagen

- `.env.local.example`: lokale Demo-/Paper-Entwicklung; Demo-, Fixture- und Fake-Pfade sind hier erlaubt.
- `.env.demo.example`: lokaler Bitget-Demo-Modus (`EXECUTION_MODE=bitget_demo`, Demogeld, kein Echtgeld).
- `.env.shadow.example`: produktionsnahes Shadow-Profil; reale Hosts, keine Demo-/Fixture-/Fake-Defaults, keine Live-Orderfreigabe.
- `.env.production.example`: Produktionsprofil; reale Hosts, keine Demo-/Fixture-/Fake-Defaults, `EXECUTION_MODE=shadow` als sicherer Default.
- `.env.test.example`: deterministische Tests; isolierte Test-DSNs, Fake-/Fixture-Pfade nur fuer Testzwecke.

## Bitget Demo-Modus mit Demogeld

1. `cp .env.demo.example .env.demo`
2. `python scripts/bitget_demo_readiness.py --env-file .env.demo --mode readonly --output-md reports/bitget_demo_readiness.md`
3. `docker compose --env-file .env.demo up --build`
4. Main Console: `http://localhost:3000`
5. API-Gateway: `http://localhost:8000`
6. Demo-Stack-Pruefung:
   `python scripts/demo_stack_healthcheck.py --env-file .env.demo --dashboard-url http://localhost:3000 --base-url http://localhost:8000 --output-md reports/demo_stack_healthcheck.md`
7. Demo-Stress-Smoke:
   `python scripts/demo_stress_smoke.py --base-url http://localhost:8000 --dashboard-url http://localhost:3000 --duration-sec 60 --output-md reports/demo_stress_smoke.md`

Sicherheitsregel: Demo-Modus bleibt strikt ohne Echtgeld. `LIVE_TRADE_ENABLE` muss `false` bleiben.

Die Profilauflösung folgt repo-weit derselben Priorität: `CONFIG_ENV_FILE` → `COMPOSE_ENV_FILE` → `ENV_PROFILE_FILE` → `STACK_PROFILE` / `APP_ENV` → `.env.local`.

## Pflichtwerte pro Profil

- `local`: `PRODUCTION=false`, `EXECUTION_MODE=paper`, `STRATEGY_EXEC_MODE=manual`, `SHADOW_TRADE_ENABLE=false`, `LIVE_TRADE_ENABLE=false`, `API_AUTH_MODE=none`, `BITGET_DEMO_ENABLED=true`, `PAPER_SIM_MODE=true`, `PAPER_CONTRACT_CONFIG_MODE=fixture`, `NEWS_FIXTURE_MODE=true`, `LLM_USE_FAKE_PROVIDER=true`, `TELEGRAM_DRY_RUN=true`.
- `shadow`: `PRODUCTION=true`, `EXECUTION_MODE=shadow`, `STRATEGY_EXEC_MODE=manual`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false`, `API_AUTH_MODE=api_key`, `BITGET_DEMO_ENABLED=false`, `PAPER_SIM_MODE=false`, `PAPER_CONTRACT_CONFIG_MODE=live`, `NEWS_FIXTURE_MODE=false`, `LLM_USE_FAKE_PROVIDER=false`, reale interne Hosts statt `localhost`.
- `production`: `PRODUCTION=true`, `DEBUG=false`, `LOG_FORMAT=json`, `VAULT_MODE=hashicorp|aws`, `EXECUTION_MODE=shadow`, `STRATEGY_EXEC_MODE=manual`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false`, `API_AUTH_MODE=api_key`, `BITGET_DEMO_ENABLED=false`, `PAPER_SIM_MODE=false`, `PAPER_CONTRACT_CONFIG_MODE=live`, `NEWS_FIXTURE_MODE=false`, `LLM_USE_FAKE_PROVIDER=false`, `TELEGRAM_DRY_RUN=false`, `NODE_ENV=production`, `NEXT_PUBLIC_ENABLE_ADMIN=false`, `APP_BASE_URL`, `FRONTEND_URL`, `DATABASE_URL`, `REDIS_URL` und `CORS_ALLOW_ORIGINS` muessen auf echte Hosts zeigen.
- `test`: `PRODUCTION=false`, `APP_ENV=test`, `CI=true`, `NODE_ENV=test`, `EXECUTION_MODE=paper`, `STRATEGY_EXEC_MODE=manual`, `SHADOW_TRADE_ENABLE=false`, `LIVE_TRADE_ENABLE=false`, `API_AUTH_MODE=none`, `TEST_DATABASE_URL` und `TEST_REDIS_URL` muessen auf die Test-Infrastruktur zeigen; deterministische Fake-/Fixture-Pfade bleiben hier erlaubt.

## Compose-Stack

Kanonische Laufzeitbeschreibung (Basis vs. Host-Port-Overlay, local/shadow/production): **`docs/compose_runtime.md`**.

Der Default-Compose-Stack bildet die volle Pipeline im Monorepo ab:

- `postgres`, `redis`
- `market-stream`, `feature-engine`, `structure-engine`, `drawing-engine`, `signal-engine`
- `news-engine`, `llm-orchestrator`
- `paper-broker`, `learning-engine`
- `api-gateway`, `alert-engine`, `monitor-engine`
- `live-broker` als Repo-interne Control-Plane fuer Upstream-Readiness
- `dashboard` als produktiver Next.js-Build mit `next build` (**standalone**) und Start ueber `node build/standalone/apps/dashboard/server.js` (siehe `apps/dashboard/Dockerfile` und `package.json` `start`)

Alle Services lesen dasselbe Profil ueber `COMPOSE_ENV_FILE`; interne Compose-Overrides verdrahten Health-URLs, den Live-Broker-Read-Path, die Alert-/Monitor-Ops-Sicht und die serverseitige Dashboard-zu-Gateway-Verbindung auf Container-Adressen. Fuer das Dashboard bleibt `NEXT_PUBLIC_API_BASE_URL` oeffentlich/browserseitig, waehrend Compose serverseitig `API_GATEWAY_URL=http://api-gateway:8000` setzt.

## Startvarianten

Vor jedem Start ein echtes Runtime-Profil anlegen, zum Beispiel:

1. `.env.local.example` -> `.env.local`
2. `.env.shadow.example` -> `.env.shadow`
3. `.env.production.example` -> `.env.production`

Die Wrapper unter `scripts/` sind Bash-basiert; auf Windows daher via WSL oder Git Bash nutzen. Ohne Bash bleibt die manuelle Compose-Reihenfolge aus diesem Dokument der Fallback.

Danach den Stack jeweils mit demselben Profil sowohl fuer Compose-Interpolation als auch fuer die Container starten:

- `local`: `bash scripts/start_local.sh`
- `shadow`: `bash scripts/start_shadow.sh`
- `production`: `bash scripts/start_production.sh`
- kompatibel/parametrisiert: `bash scripts/start_all.sh local|shadow|production`
- optional Observability: `bash scripts/start_production.sh --with-observability` bzw. entsprechender Wrapper

Unter PowerShell entsprechend:

- `bash scripts/start_local.sh`
- `bash scripts/start_shadow.sh`
- `bash scripts/start_production.sh`
- oder: `$env:STACK_PROFILE="shadow"; bash scripts/start_all.sh`

## Startreihenfolge

Die operative Reihenfolge ist jetzt fest in `scripts/bootstrap_stack.sh` verankert:

1. Datastores hochfahren oder externe Datastores gegen `DATABASE_URL` / `REDIS_URL` pruefen.
2. Migrationen mit `infra/migrate.py` gegen die Host-/Ops-DSN ausfuehren.
3. Kernbasis starten: `market-stream`, `llm-orchestrator`.
4. Kern-Ingestion/Analyse starten: `feature-engine`, `structure-engine`, `news-engine`.
5. Kern-Signalpfad starten: `drawing-engine`, `signal-engine`.
6. Broker-/Live-Slot: `paper-broker`, `live-broker`, danach `learning-engine`.
7. `alert-engine` **vor** `api-gateway` (Compose-Abhaengigkeit).
8. `api-gateway`, danach `monitor-engine` (Monitor baut auf Gateway auf).
9. Optional Observability: `prometheus`, `grafana` (Profil `observability`).
10. `dashboard`, abschliessend `scripts/healthcheck.sh` (mit Retries / optional `HEALTHCHECK_EDGE_ONLY`).

Detailtabelle Readiness/Liveness: **`docs/stack_readiness.md`**.

### Observability (Prometheus / Grafana)

- Konfiguration: `infra/observability/prometheus.yml`, Alertregeln `infra/observability/prometheus-alerts.yml`, Grafana-Provisioning unter `infra/observability/grafana/`.
- Detailmetriken, Alertliste und Betriebshinweise: **`docs/observability.md`**.
- Start: `docker compose --profile observability up -d prometheus grafana` mit demselben `COMPOSE_ENV_FILE` wie der Stack, oder `WITH_OBSERVABILITY=true` bei den `scripts/start_*.sh`-Wrappern.

Die angefragte Reihenfolge wurde bewusst in eine lauffaehige Form normalisiert: Migrationen laufen unmittelbar nach erreichbaren Datastores, weil ohne erreichbare Postgres-Instanz keine reproduzierbare Migration moeglich ist.

## Ablauf (Compose auf einem Server)

1. `.env.production.example` auf dem Host nach `.env.production` kopieren (nicht committen); Secrets aus Vault exportieren **in RAM** oder als Docker-Secrets. Hinweis: die Vorlage ist aktuell auf reale interne Hostnamen / cluster-aehnliche DNS-Namen ausgelegt; fuer reines Single-Host-Compose muessen interne DSNs und `*_URL`-Ziele explizit an die echte Laufzeit angepasst werden.
2. Optional: `WITH_OBSERVABILITY=true bash scripts/start_production.sh`
3. Alternativ ohne Wrapper: `COMPOSE_ENV_FILE=.env.production docker compose --env-file .env.production build --no-cache`
4. Danach dieselbe Reihenfolge wie in `scripts/bootstrap_stack.sh` einhalten.
5. Smoke: `scripts/healthcheck.sh` mit gesetzten URLs (`API_GATEWAY_URL`, `MARKET_STREAM_URL`, `FEATURE_ENGINE_URL`, `STRUCTURE_ENGINE_URL`, `DRAWING_ENGINE_URL`, `SIGNAL_ENGINE_URL`, `NEWS_ENGINE_URL`, `LLM_ORCH_URL`, `PAPER_BROKER_URL`, `LEARNING_ENGINE_URL`, `ALERT_ENGINE_URL`, `MONITOR_ENGINE_URL`, `LIVE_BROKER_URL`, `DASHBOARD_URL`)

## Kubernetes / Swarm (Skizze)

- **Swarm:** `docker stack deploy -c docker-compose.yml bitget` (Compose-Datei ggf. anpassen: keine Host-Ports, Overlay-Netz).
- **Kubernetes:** Pro Service ein Deployment + Service; ConfigMaps fuer nicht-sensible ENV, **Secrets** fuer DSN/Keys; Ingress nur mit TLS.

## Rollback

1. Vor Deploy: notiere laufendes Image-Tag (z. B. `docker compose images`).
2. Bei Fehler: `docker compose pull` mit vorherigem Tag oder `docker compose up -d` mit `image: ...@sha256:...`.
3. DB: nur bei kompatiblen Migrationen zurueckrollen; sonst Restore aus Backup.

## Post-Deployment

- `scripts/healthcheck.sh`
- Stichprobe: `GET /health`, `GET /ready`, `GET /v1/system/health`; sensible Pfade nur mit gueltiger Auth (`docs/api_gateway_security.md`), z. B. `GET /v1/live-broker/runtime`, `GET /v1/monitor/alerts/open`.
- Logs: bei `LOG_FORMAT=json` in ELK/Loki/Grafana Loki parsen; Metriken: `docs/observability.md`

## DSGVO / MiCA

Keine personenbezogenen Daten in Logs. Wenn Nutzerdaten verarbeitet werden, Zweck, Rechtsgrundlage und Aufbewahrung dokumentieren.

## API-Gateway-Absicherung (Ist-Stand)

Sensible Routen sind mit **JWT (HS256)** und/oder **internem API-Key** absicherbar; bei `PRODUCTION=true` oder `GATEWAY_ENFORCE_SENSITIVE_AUTH=true` sind Credentials Pflicht. Rate-Limits (Redis) und Audit-Logging sind integriert. Erweiterungen (OAuth2-Introspection, mTLS-Claims) sind strukturell vorgesehen — siehe **`docs/api_gateway_security.md`**.

## Go-Live-Reihenfolge (Kurz)

1. Stabil **shadow** mit realem Stack (keine Demo-Defaults), Observability aktiv, Alerts gruen.
2. Risk- und Leverage-Parameter verifizieren (`RISK_*`, 7x-Freigabe-Regeln).
3. **Live** nur nach Checkliste: `docs/LaunchChecklist.md` und `docs/prod_runbook.md`.
4. Live-Broker-, Registry- und Drift-Dokumentation: `docs/live_broker.md`, `docs/model_stack_v2.md`, `docs/shadow_live_divergence.md`, `docs/online_drift.md`.
