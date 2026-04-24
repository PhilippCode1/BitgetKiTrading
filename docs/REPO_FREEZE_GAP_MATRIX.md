# Repo Freeze, Gap-Matrix und Abschluss-Backlog

**Stand:** 2026-04-24 (P83 Dokumentations-Paritaet; Roadmap 1–10: `docs/ROADMAP_10_10_CLOSEOUT.md`).

## Freeze-Update 2026-03-29

Die aktuelle Truth-Matrix steht in `docs/REPO_TRUTH_MATRIX.md`. Dieses Dokument ist die
kanonische Gap-Matrix fuer den eingefrorenen Ausgangszustand vor weiteren grossen Umbauten.

**Kanonischer Zielzustand fuer die Folgearbeit:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`

### P0 — Produktionsblocker

| Thema                                                              | Typ                                                                                                                                                                                | Schwere                                                                                   | Evidenz                                                                                                        |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Paper-Broker Contract bei `live`-Mode                              | In **shadow/production** (`app_env` oder `production`) **kein** Fixture-Fallback bei REST-Fehler (`RuntimeError`); Fixture nur bei `mode=fixture` oder lokaler Nicht-Prod-Umgebung | erledigt (Code+Test)                                                                      | `contract_config.py` (`_fixture_fallback_allowed`), `tests/paper_broker/test_contract_config_family_matrix.py` |
| BTCUSDT-/USDT-FUTURES-Reste in Fixtures, Beispiel-ENV, Doku, Tests | Drift-/Verwechslungsrisiko, nicht automatischer Live-Default                                                                                                                       | **erledigt (P83)** — Multi-Asset-Factory/Katalog, Doku bereinigt, keine P0-Blocker in der Matrix | `MarketInstrumentFactory` / `BitgetInstrumentIdentity` (`shared_py/bitget/instruments.py`), `config/settings.py`, Truth-Matrix, `docs/SYSTEM_AUDIT_MASTER.md` |

### P1 — Hohe Release-Relevanz

| Thema                                                                                    | Typ                                                                                                  | Schwere       | Evidenz                                                                                                                                 |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Event-Determinismus / Replay                                                             | Kern-Envelope + Tests verbessert (Stufe 4); institutionelle Vollabdeckung aller Event-Typen iterativ | medium (Rest) | `shared/python/src/shared_py/eventbus/envelope.py`, `docs/replay_determinism.md`                                                        |
| `.env.production.example` driftet zu cluster-/externem Betrieb statt Single-Host-Compose | Deploy-/Ops-Drift                                                                                    | medium        | `.env.production.example`, `docs/Deploy.md`                                                                                             |
| Service-`pyproject.toml` mit Versionsranges                                              | editable-Dev ok; **Release-Images/CI** muessen `-c constraints-runtime.txt` erzwingen                | medium        | `constraints-runtime.txt`, `services/*/pyproject.toml`, `docs/release_build.md`                                                         |
| ~~Security-Audits in CI nicht blockierend~~                                              | ~~Release-Gate-Luecke~~                                                                              | ~~medium~~    | **erledigt:** `pip_audit_supply_chain_gate.py`, `check_production_env_template_security.py` in `.github/workflows/ci.yml` (blockierend) |
| Coverage-/Schema-Gates nicht repo-weit gleichmaessig                                     | Release-Gate-Luecke                                                                                  | medium        | `.coveragerc`, `tools/check_coverage_gates.py`, `tests/dashboard/*.sh`                                                                  |
| ~~Grafana-Dashboards im Repo weitgehend Platzhalter~~                                    | ~~Observability-Luecke~~                                                                             | ~~medium~~    | **erledigt:** `infra/observability/grafana/dashboards/*.json`, Manifest `dashboards.json`, Stufe 7                                      |

### P2 — Dokumentation / Nachzug / technische Schulden

| Thema                                                                                            | Typ               | Schwere | Evidenz                                                                                                                            |
| ------------------------------------------------------------------------------------------------ | ----------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| README-/Runbook-Startreihenfolge musste korrigiert werden                                        | Doc-Drift         | minor   | `README.md`, `docs/Deploy.md`, `docker-compose.yml`                                                                                |
| Shared TS / OpenAPI / Event-Payload-Paritaet nicht vollstaendig                                  | technische Schuld | medium  | `shared/ts/`, `shared/contracts/openapi/`, `shared/contracts/schemas/`                                                             |
| Instrumentenkatalog / Metadatenservice noch nicht repo-weit in alle Servicepfade durchverdrahtet | technische Schuld | medium  | `shared/python/src/shared_py/bitget/catalog.py`, `shared/python/src/shared_py/bitget/metadata.py`, `services/*`, `apps/dashboard/` |

### Freeze-Regel

**P83 (2026-04-24):** Die **P0-Software-Blocker** in dieser Matrix sind im Repo-Stand abgeschlossen; verbleibende Eintraege sind **P1/P2** (iterativ) oder **akzeptierte Restrisiken** (`docs/adr/ADR-0010-roadmap-accepted-residual-risks.md`). **Externe** Go-Live-Punkte (Exchange, Recht, Betrieb) sind nicht Gegenstand dieser Matrix. Aenderungen an Code/Compose werden weiterhin gegen `docs/REPO_TRUTH_MATRIX.md`, diese Matrix und ADR-0001 begruendet.

**Zweck:** Eine **kanonische Freeze-Referenz** fuer alle Folgeprompts: reale Verzeichnisse, Abgleich mit `infra/service-manifest.yaml` und `docker-compose.yml`, priorisierte Luecken und Zuordnung zu Folgeprompt-Bloecken.

---

## Verbindliche Arbeitsregeln (Freeze)

- Nur dieses Monorepo; kein Ersatz-Repo, keine Parallelarchitektur ausserhalb.
- **Betriebsmodi:** `paper`, `shadow`, `live` — siehe Abschnitt [Betriebsmodi](#verbindliche-betriebsmodi-paper-shadow-live).
- **Trading-Kern:** deterministische Safety-Layer, Quant/ML, Risk, Uncertainty, Gating; **kein LLM-only-Trading**.
- **Hebel:** nur Integer **7..75**; ohne saubere **7x**-Freigabe (wenn Policy aktiv) Ziel **`do_not_trade`** / Block im Live-Pfad.
- **Produktionsziel:** keine Demo-/Fake-/Fixture-Defaults in Shadow/Prod-Profilen; keine Secrets im Repo/FE/Logs; kein Dev-Server im Prod-Image (`pnpm dev`); Kern-Images ohne `latest`-Pins wo verbindlich verlangt.
- **Konfliktloesung:** weichen Manifest, Compose, zentrale Docs und Code voneinander ab, gilt die **Laufzeitwahrheit im Code und in Compose**; diese Matrix und betroffene Docs sind nachzuziehen.

---

## Verbindliche Betriebsmodi (paper, shadow, live)

| Modus (Konzept) | Typische ENV (siehe `.env.*.example`)                                          | Kurz (Ist-Code)                                                                                                                                                                      |
| --------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **paper**       | `EXECUTION_MODE=paper`, `SHADOW_TRADE_ENABLE=false`, `LIVE_TRADE_ENABLE=false` | Paper-Pfad ueber `services/paper-broker/`; Live-Broker konsumiert Signale im Worker nur ausserhalb von `paper_path_active` (siehe `services/live-broker/src/live_broker/worker.py`). |
| **shadow**      | `EXECUTION_MODE=shadow`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false` | Gleiche Entscheidungsketten wie Live-Candidate ohne Order-Submit; Gates in `services/live-broker/src/live_broker/execution/service.py` (z. B. `live_allow_order_submit`).            |
| **live**        | `EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true`, `LIVE_BROKER_ENABLED=true`    | Echte Submits nur mit allen Gates (Risk, Exchange-Health, optional Shadow-Match, Drift, 7x-Approval); siehe `config/settings.py` und Live-Broker.                                    |

**Quellen im Repo:** `config/settings.py` (`BaseServiceSettings`), `.env.local.example`, `.env.shadow.example`, `.env.production.example`, `docs/Deploy.md`, `docs/LaunchChecklist.md`, `docs/live_broker.md`.

---

## Abgleichsquellen (Reihenfolge)

1. **Laufzeit-Topologie:** `docker-compose.yml` (inkl. Profile `observability`).
2. **Service-Inventur / ENV-Pflichtfelder:** `infra/service-manifest.yaml`.
3. **Globale Policy und Profil-Validatoren:** `config/settings.py`, `config/gateway_settings.py`, `config/bootstrap.py`.
4. **Operative Runbooks / Deploy:** `docs/Deploy.md`, `docs/LaunchChecklist.md`, `docs/prod_runbook.md`, `docs/monitoring_runbook.md`, `scripts/*.sh`.
5. **Architektur-Audit (Verweis):** `docs/SYSTEM_AUDIT_MASTER.md` — zeigt nur auf Truth-/Gap-Matrizen (kein eigener Befundtext mehr).

---

## Inventar: reale Pfade

### Services (`services/`)

Unter `services/` existieren **13** Microservices, jeweils mit `Dockerfile` und Python-Paket unter `src/<paket>/`.

| Service          | Ordner                      | `Dockerfile` | In `docker-compose.yml` | Container-Start (Dockerfile `CMD`) | `app.py` (FastAPI) | `main.py`                |
| ---------------- | --------------------------- | ------------ | ----------------------- | ---------------------------------- | ------------------ | ------------------------ |
| api-gateway      | `services/api-gateway`      | ja           | ja                      | `python -m api_gateway.app`        | ja                 | nein (Start ueber `app`) |
| market-stream    | `services/market-stream`    | ja           | ja                      | `python -m market_stream.main`     | ja                 | ja                       |
| feature-engine   | `services/feature-engine`   | ja           | ja                      | `python -m feature_engine.main`    | ja                 | ja                       |
| structure-engine | `services/structure-engine` | ja           | ja                      | `python -m structure_engine.main`  | ja                 | ja                       |
| drawing-engine   | `services/drawing-engine`   | ja           | ja                      | `python -m drawing_engine.main`    | ja                 | ja                       |
| signal-engine    | `services/signal-engine`    | ja           | ja                      | `python -m signal_engine.main`     | ja                 | ja                       |
| news-engine      | `services/news-engine`      | ja           | ja                      | `python -m news_engine.main`       | ja                 | ja                       |
| llm-orchestrator | `services/llm-orchestrator` | ja           | ja                      | `python -m llm_orchestrator.main`  | ja                 | ja                       |
| paper-broker     | `services/paper-broker`     | ja           | ja                      | `python -m paper_broker.main`      | ja                 | ja                       |
| learning-engine  | `services/learning-engine`  | ja           | ja                      | `python -m learning_engine.main`   | ja                 | ja                       |
| live-broker      | `services/live-broker`      | ja           | ja                      | `python -m live_broker.main`       | ja                 | ja                       |
| alert-engine     | `services/alert-engine`     | ja           | ja                      | `python -m alert_engine.main`      | ja                 | ja                       |
| monitor-engine   | `services/monitor-engine`   | ja           | ja                      | `python -m monitor_engine.main`    | ja                 | ja                       |

**Infra + Observability:** `postgres` / `redis` sind unter `infrastructure:` in `infra/service-manifest.yaml` erfasst (Images wie in Compose: `postgres:16.6-alpine`, `redis:7.4.2-alpine`). Optional im Compose-Profil `observability`: `prom/prometheus:v2.54.1`, `grafana/grafana:11.2.0` — siehe `compose_runtime` im Manifest und `docs/compose_runtime.md`.

**Dashboard:** `apps/dashboard/` — in `docker-compose.yml` und im Manifest; Prod-Image: **standalone** (`Dockerfile` → `CMD ["node", "apps/dashboard/server.js"]`).

### Shared Code

| Bereich                 | Pfad                                          | Befund                                                                                                    |
| ----------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Shared Python (Runtime) | `shared/python/src/shared_py/`                | **real vorhanden** — Eventbus, Risk, Leverage, Bitget-HTTP, Observability, Drift/Shadow-Live-Hilfen u. a. |
| Shared Python Tests     | `shared/python/tests/`                        | **real vorhanden**                                                                                        |
| Shared TS               | `shared/ts/` (`src/index.ts`, `package.json`) | **teilweise** — duenne Exports, Stub-Konstante im Index                                                   |
| Workspace-Python-Paket  | `shared/python/pyproject.toml`                | **real vorhanden**                                                                                        |

### Contracts

| Bereich                | Pfad                                                               | Befund                                                                     |
| ---------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| JSON-Schemas (App)     | `shared/contracts/schemas/*.schema.json`                           | **real vorhanden** (u. a. `news_summary`, `signal_explanation`, `drawing`) |
| Contract-README        | `shared/contracts/README.md`, `shared/contracts/schemas/README.md` | **real vorhanden**                                                         |
| Test-/Tool-Schemas     | `infra/tests/schemas/*.schema.json`                                | **real vorhanden** (Gateway/Fixture-Checks)                                |
| Top-Level `contracts/` | —                                                                  | **fehlt** (kein zweiter Root; Kanon bleibt `shared/contracts/`)            |

### Dashboard

| Pfad                              | Befund                                                                                                                                                                                                |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/dashboard/`                 | **real vorhanden** — Next.js, Prod-Image Multi-Stage: `pnpm` / `next build` mit `output: standalone`, Start **`node build/standalone/apps/dashboard/server.js`** (kein `next start` im Release-Image) |
| `apps/dashboard/src/app/page.tsx` | **real vorhanden** (Manifest-„entrypoint“-Hinweis auf UI-Einstieg)                                                                                                                                    |

### Infra

| Pfad                                        | Befund                                                                                                                                      |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `infra/service-manifest.yaml`               | **real vorhanden**                                                                                                                          |
| `infra/migrations/postgres/*.sql`           | **65** Dateien, **real vorhanden**                                                                                                          |
| `infra/migrate.py`                          | **real vorhanden** (Root; in Doku referenziert)                                                                                             |
| `infra/observability/prometheus.yml`        | **real vorhanden** — Scrapes fuer **alle** Kern-Services inkl. Pipeline                                                                     |
| `infra/observability/prometheus-alerts.yml` | **real vorhanden**                                                                                                                          |
| `infra/observability/grafana/`              | **real vorhanden** — Provisioning; `dashboards/` mit Trading-Ops + SLI/Security; `dashboards.json` = Dashboard-Manifest (kein leeres Array) |
| `infra/ci/ci_pipeline.yml`                  | **real vorhanden**                                                                                                                          |
| `infra/tests/docker-compose.test.yml`       | **real vorhanden**                                                                                                                          |

### Tests

| Pfad                                | Befund                                                                  |
| ----------------------------------- | ----------------------------------------------------------------------- |
| `tests/`                            | **real vorhanden** — unit, integration, service-spezifische Unterordner |
| `tests/market-stream/`              | **real vorhanden** (Bindestrich im Pfad; Paket heisst `market_stream`)  |
| `tests/dashboard/*.sh`              | **real vorhanden** — Shell-Smokes                                       |
| `shared/python/tests/`              | **real vorhanden**                                                      |
| `apps/dashboard/src/lib/__tests__/` | **real vorhanden** (Jest)                                               |

### Tools und Skripte (Runbook-naehe)

| Pfad                                                    | Befund                                                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `tools/*.py`                                            | **real vorhanden** — u. a. `check_schema.py`, `check_coverage_gates.py`, Stream/Fixture-Publisher |
| `scripts/healthcheck.sh`                                | **real vorhanden** — Ready-Kette + `GET /v1/system/health`                                        |
| `scripts/bootstrap_stack.sh`, `start_*.sh`, `deploy.sh` | **real vorhanden**                                                                                |
| `scripts/integration_compose_smoke.sh`                  | **real vorhanden**                                                                                |

### CI

| Pfad                       | Befund                                                                                                                             |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `.github/workflows/ci.yml` | **real vorhanden** — Ruff/Black, Migrate, Pytest, `check_coverage_gates.py`, Dashboard npm, `docker compose up` + `healthcheck.sh` |

### Zentrale Doku (Auszug)

Unter `docs/` liegen **ueber 90** Markdown-Dateien, u. a.: `Deploy.md`, `LaunchChecklist.md`, `prod_runbook.md`, `monitoring_runbook.md`, `api_gateway_security.md`, `live_broker.md`, `TESTING_AND_EVIDENCE.md`, `REPO_SBOM_AND_RELEASE_METADATA.md`, `RELEASE_CLEANUP_REPORT.md`, `SYSTEM_AUDIT_MASTER.md` (Verweis), domaenenspezifisch (`signal_engine.md`, `paper_broker.md`, …).

---

## Status-Legende fuer Bloecke

| Markierung           | Bedeutung                                                               |
| -------------------- | ----------------------------------------------------------------------- |
| **real vorhanden**   | Pfad/Funktion im Repo nachweisbar, mit Laufzeitbezug.                   |
| **teilweise**        | Kern da, aber Luecken (Stubs, unvollstaendige Abdeckung, Profil-Drift). |
| **nur dokumentiert** | Anforderung nur in Doku/Manifest, ohne vollstaendige Code-Abbildung.    |
| **veraltet**         | Doku oder Manifest widerspricht Compose/Code-Stand.                     |
| **doppelt**          | Gleiche Information an mehreren Stellen mit Risiko fuer Drift.          |
| **widerspruechlich** | Zwei kanonische Quellen liefern unterschiedliche Aussagen.              |

---

## Abgleich: Manifest vs Compose vs Code

| Thema                                    | Manifest                                                  | Compose / Code                                                                                       | Status                                                                                           |
| ---------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Kern-Pipeline in Containern              | Alle genannten Services inventarisiert                    | `docker-compose.yml` startet **alle 13** Python-Services + Dashboard + Datenstores                   | **real vorhanden**; fruehere Audit-Phasen mit gegenteiliger Behauptung **entfernt** (2026-03-30) |
| `market-stream` HTTP-Port / Host-Publish | Manifest `http_port: 8010`, `host_publish: false`         | Compose-Basis: **8010 nur intern**; Host-Mapping nur mit `docker-compose.local-publish.yml`          | **abgestimmt** (siehe `docs/compose_runtime.md`)                                                 |
| `api-gateway` Entry                      | `app.py`                                                  | `CMD` → `api_gateway.app`                                                                            | **real vorhanden**, konsistent                                                                   |
| Uebrige Services Entry                   | meist `main.py`                                           | `CMD` → `*.main`                                                                                     | **real vorhanden**, konsistent                                                                   |
| Live-Broker Private-WS                   | `operational_constraints.note` u. a. „Private-WS-… offen“ | `services/live-broker/src/live_broker/private_ws/`, Start in `app.py`                                | **veraltet** im Manifest-Text; technische Luecke eher **Reconcile/Tiefe**, nicht „kein WS“       |
| Default `env_files` im Manifest          | nur `.env.local`                                          | Compose: `COMPOSE_ENV_FILE` → `.env.local` default; Shadow/Prod laut `docs/Deploy.md` andere Dateien | **doppelt / widerspruechlich** zur Profil-Doku                                                   |
| Postgres/Redis-Image-Tags                | `infrastructure` im Manifest                              | `docker-compose.yml`: `postgres:16.6-alpine`, `redis:7.4.2-alpine`                                   | **abgestimmt**                                                                                   |

---

## Gap-Matrix nach Bloecken

Prioritaeten: **P0** = Produktionsblocker / harte Sicherheits- oder Policy-Luecke; **P1** = hohe Release-Relevanz; **P2** = nachziehen nach P0/P1.

| Block                        | Reale Ankerpfade                                                                                                                                           | Status                               | Kurz-Befund                                                                                                                                                                                                                                                                                                             | Prio   | Folgeprompt / Block                                                                            |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------- |
| **Config / Profile**         | `config/settings.py`, `config/bootstrap.py`, `config/gateway_settings.py`, `services/*/config.py` + `settings.py`/`app.py` mit `env_file`, `.env*.example` | **teilweise** / **widerspruechlich** | Viele Services laden explizit `(_REPO_ROOT)/.env.local` als `env_file`; Shadow/Prod-Profile sind in Doku gefordert, aber nicht ueberall profil-neutral. Zusaetzlich: `RISK_ALLOWED_LEVERAGE_MAX` ist in `BaseServiceSettings` auf **exakt 75** validiert — widerspricht `docs/LaunchChecklist.md` (Erst-Burn-in **7**). | **P0** | **Prompt 02** (Config/Profile-Freeze, Validatoren); **Prompt 07** (Hebel-Policy vs Checkliste) |
| **Paper-Broker Contract**    | `services/paper-broker/src/paper_broker/engine/contract_config.py`                                                                                         | **abgestimmt (Prod-like)**           | `live` + Fetch-Fehler: in shadow/prod **fail-closed**; `fixture`-Mode bleibt explizit fuer Dev/Test.                                                                                                                                                                                                                    | **P2** | laufend                                                                                        |
| **Risk / do_not_trade / 7x** | `shared/python/src/shared_py/risk_engine.py`, `services/signal-engine/.../hybrid_decision.py`, `services/live-broker/.../execution/service.py`             | **real vorhanden** / **teilweise**   | `do_not_trade` und Integer-Leverage sind im Kern verdrahtet; Live-Broker blockt **7x** ohne `approved_7x`. Gap: zentrale ENV-Policy vs operative Obergrenze (siehe Config-Zeile).                                                                                                                                       | **P0** | **Prompt 07**                                                                                  |
| **Manifest vs Laufzeit**     | `infra/service-manifest.yaml`                                                                                                                              | **abgestimmt** (Compose-Prompt 05)   | Ports, `depends_on`, `host_publish` und `compose_runtime` folgen `docker-compose.yml` / Overlay; Live-Broker-`operational_constraints` ggf. laufend bei WS-Reconcile verfeinern.                                                                                                                                        | **P2** | laufend                                                                                        |
| **Audit-Doku**               | `docs/SYSTEM_AUDIT_MASTER.md`                                                                                                                              | **abgestimmt**                       | Verweisdokument ohne widersprüchliche Phasen-Tabellen; Kanon bleibt Truth-/Gap-Matrix.                                                                                                                                                                                                                                  | **P2** | laufend bei grossen Architekturaenderungen                                                     |
| **Determinismus / Replay**   | `shared/python/src/shared_py/eventbus/envelope.py`, `services/llm-orchestrator/.../retry/backoff.py`                                                       | **verbessert**                       | Envelope-Replay-Validator (Prompt 4); LLM-Backoff **ohne RNG** (`sleep_backoff`).                                                                                                                                                                                                                                       | **P2** | laufend                                                                                        |
| **LLM-Nebenpfad**            | `services/llm-orchestrator/.../providers/*.py`, `constants.py`                                                                                             | **verbessert**                       | Kein Tool-Calling im Protokoll; `/health` mit `api_contract_version`; Doku/README. Modelloutput bleibt stochastisch.                                                                                                                                                                                                    | **P2** | laufend                                                                                        |
| **Security Boundary**        | `docker-compose.yml` + `docker-compose.local-publish.yml`                                                                                                  | **teilweise**                        | Basis-Compose: nur **Gateway (8000)** und **Dashboard (3000)** auf dem Host; Pipeline intern. Overlay **local-publish** oeffnet Dev/CI-Ports bewusst — in Shadow/Prod ohne Overlay weglassen und Health ueber Gateway/intern. Gateway-Auth weiterhin **P1**-Thema (`Prompt 03`).                                        | **P1** | **Prompt 03** (Auth); Overlay-Disziplin in Runbooks                                            |
| **Observability**            | `infra/observability/prometheus.yml`, `grafana/dashboards/`, `shared/python/.../metrics.py`                                                                | **verbessert**                       | Prometheus-Scrape **real**; `bitget-trading-ops.json` mit Gateway→Live-Broker, Pipeline-Latenz/No-Trade, Worker-Heartbeat-Alter; `touch_worker_heartbeat` in Pipeline-/Alert-/Paper-/Learning-Workern, Monitor-Tick, Market-Stream Feed-Health.                                                                         | **P2** | laufend (Feintuning Alerts/SLO)                                                                |
| **Tests / Coverage**         | `pyproject.toml`, `.coveragerc`, `tools/check_coverage_gates.py`, `.github/workflows/ci.yml`                                                               | **verbessert**                       | Wie oben; zusaetzlich Integrationsnachweise Live-Broker Reconcile/Recovery/Health (`tests/integration/test_http_stack_recovery.py`, `test_db_live_recovery_contracts.py`). Voller Chaos gegen Exchange bleibt Staging.                                                                                                  | **P2** | laufend / Staging-Soak                                                                         |
| **Contracts FE/BE**          | `shared/contracts/catalog/event_streams.json`, `schemas/`, `openapi/`, `shared/ts`, `tools/check_contracts.py`, `docs/contracts_extension.md`              | **verbessert**                       | Katalog ↔ TS (`eventStreams.ts`) ↔ Schema-Enum und OpenAPI-Grundstruktur blockieren per `check_contracts.py`; Pytest `test_openapi_export_sync` haelt Export synchron. Payload-Schemas / Gateway-Response-Typing weiter iterativ.                                                                                       | **P2** | laufend                                                                                        |
| **Live-Broker Tiefe**        | `services/live-broker/` (REST, Private-WS, Reconcile, Worker)                                                                                              | **verbessert**                       | Runtime **real**; Integration: Reconcile-HTTP-Vertrag + DB FK `reconcile_runs`↔`reconcile_snapshots` + Ops-Summary-Tests; Runbook §8. Exchange-Tiefen-Nachweis (echte Bitget-Orders) bleibt staging-/umgebungsabhaengig.                                                                                                | **P2** | laufend / Staging                                                                              |

---

## P0 / P1 / P2 — kompakte Prioritaetenliste

### P0

1. **Profil- und ENV-Ladeverhalten:** `.env.local`-Pin in mehreren Service-Settings vs dokumentierte Profile (`COMPOSE_ENV_FILE`, `.env.shadow` / `.env.production`).
2. ~~**Paper Contract live + Fixture-Fallback**~~ — **erledigt** fuer prod-like `app_env` (Tests: `test_contract_config_live_fetch_fails_closed_in_shadow`).

### P1

4. ~~**`infra/service-manifest.yaml`:** Manifest-Sync~~ — siehe Prompt 05 (erledigt); Live-Broker-Notizen ggf. laufend.
5. ~~**`docs/SYSTEM_AUDIT_MASTER.md`:** Compose-Tabelle sync~~ — **erledigt** (Verweisdokument, 2026-03-30).
6. **Determinismus:** Event-Envelope + LLM-Backoff **verbessert** (Stufe 4/5); vollstaendige Replay-Abdeckung aller Typen iterativ.
7. **LLM-Orchestrator:** `call_tools`-Stub / optionale Haertung der Rand-Schicht.
8. **Netz/Exposure:** Host-Publishing aller Service-Ports — dokumentieren und fuer Prod absichern (Betrieb, nicht nur Code).
9. ~~**Observability:** leere Grafana-Dashboards; Worker-Heartbeats.~~ — **erledigt** (Roadmap Stufe 7): Trading-Ops-Dashboard-Panels + Worker-Heartbeats.
10. **Coverage/CI:** `source`-Liste, `fail_under`-Strategie, Dashboard-Shell-Smokes in CI-Strategie.
11. ~~**Security-CI:** pip-audit / Prod-ENV-Template-Gate.~~ — **erledigt** (Stufe 6): siehe `.github/workflows/ci.yml`.

### P2

11. **Shared-TS / Contract-Sync** mit Gateway-Responses (Kern angelegt; Rest iterativ).
12. **Weitere Doku-Deduplizierung** (Runbooks vs README vs Domänendocs).

---

## Verbindlicher Folgeprompt-Backlog (Zuordnung)

| Prompt        | Schliesst primaer                                                                                                                                                        |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Prompt 02** | Config-/Profil-Freeze, Manifest-Sync, Doku-Drift (Freeze-Referenz; `SYSTEM_AUDIT_MASTER` nur noch Verweis)                                                               |
| **Prompt 03** | Security Boundary, Admin-/Debug-Routen, Netz-/Exposure-Dokumentation, zusaetzliche Prod-Guards                                                                           |
| **Prompt 04** | _(laut frueherem Backlog: Dashboard-Prod-Container — im aktuellen Repo erfuellt; nur noch Feintuning ueber andere Prompts)_                                              |
| **Prompt 05** | Contracts, Event-Kanon-Disziplin, `shared/ts` _(Katalog/Schemas/OpenAPI/Tests — erledigt; Payload-Tiefe laufend)_                                                        |
| **Prompt 06** | LLM-Determinismus, `call_tools`/Fake-Pfad-Einfrierung                                                                                                                    |
| **Prompt 07** | Risk-Governor, Hebel-Policy vs Checkliste, Paper-Contract-Verhalten in Prod                                                                                              |
| **Prompt 08** | Observability: Grafana, Heartbeats, E2E-Docker-Verifikation                                                                                                              |
| **Prompt 09** | Tests, Coverage-Quellen, CI-Gates                                                                                                                                        |
| **Prompt 10** | Abschlussaudit: `ROADMAP_10_10_CLOSEOUT.md`, Scorecard/Gap-Matrix/ADR Accepted Risk, Soak-Doku (`TESTING_AND_EVIDENCE.md`); Live-Broker Reconcile/Recovery siehe Stufe 9 |

---

## Abschlussregel fuer alle Folgeprompts

Jeder Folgeprompt liefert am Ende:

1. geaenderte Dateien
2. neue oder geaenderte ENV-Keys
3. ausgefuehrte Kommandos und Testergebnisse
4. verbleibende **externe** Blocker (Secrets, Domains, Boersenrechte) nur wenn real

---

## Stub-/Fake-/Testpfade (bewusst im Repo)

| Pfad                                                | Zweck                                     | Prod-Status                                                               |
| --------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------- |
| `NEWS_FIXTURE_MODE`, News-Sources                   | lokale/test Ingest                        | `BaseServiceSettings._prod_safety` verbietet Fixture in `PRODUCTION=true` |
| `LLM_USE_FAKE_PROVIDER`, `fake_provider.py`         | Tests / lokal                             | in Prod geblockt                                                          |
| `shared/ts/src/eventStreams.ts`, `eventEnvelope.ts` | Eventbus-Typen (Sync mit Katalog manuell) | **P2** bei neuen `event_type` mitpflegen                                  |

---

## Monorepo CI — Freeze-Status (automatisiert, Merge-Gate)

`tools/check_release_approval_gates.py` wertet **nur diese Tabelle** aus. **Status** muss
`OPEN` (Merge blockiert) oder `CLOSED` (fuer CI OK) lauten. P0/P1+OPEN brechen
`.github/workflows/ci.yml` (Job `release-approval-gate`) ab. P2+OPEN blockiert
den Merge-Job nicht.

| Prio | Status | Thema (kurz) |
| ---- | ---- | ---- |
| P0 | CLOSED | Kein offener P0-Blocker fuer Monorepo-Merge (Truth/Gates) |
| P1 | CLOSED | Kein offener P1-Release-Blocker |

---

_Ende REPO_FREEZE_GAP_MATRIX — kanonische Referenz fuer Folgeprompts._
