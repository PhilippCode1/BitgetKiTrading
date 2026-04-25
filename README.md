# bitget-btc-ai

Private deutsche Bitget-Multi-Asset-KI-Trading-Anwendung fuer Philipp Crljic mit
zentraler Main Console. Das Projekt wird nicht verkauft, hat kein Billing, keine
Kundenrollen, keine Subscription- oder Payment-Flows und keine oeffentliche
Customer Journey als Produktziel.

Monorepo fuer eine **produktionsfaehige** Pipeline: Marktdaten → Features → Struktur/Drawings → **deterministischer Signal-Kern** (Risk, Uncertainty, Gating) → Paper / **Shadow** / **Live** ueber den **Live-Broker** als Control-Plane. Das Repo ist nicht mehr nur auf `BTCUSDT`/`USDT-FUTURES` konzipiert, sondern auf ein **Bitget-Marktuniversum** mit expliziten Marktfamilien (`spot`, `margin`, `futures`), family-aware Instrumentidentitaet (u. a. `MarketInstrumentFactory` / `BitgetInstrumentIdentity` in `shared/python/src/shared_py/bitget/instruments.py`) und spezialisierten Entscheidungsstapeln. **LLM** ist unterstuetzend (z. B. News), **nicht** der alleinige Trading-Kern.

## Produktreife 10/10 (Software-Repo) und „Production Launch“

**Stand:** `10/10 erreicht` darf nicht behauptet werden, solange Evidence fehlt.
Das Repo enthaelt viele technische Grundlagen, aber echte Produktionsfreigabe,
Bitget-Keys, Recht, Security-/Restore-/Shadow-Evidence und Owner-Signoffs sind
nicht durch einen Git-Commit ersetzt. Die verbindliche Truth-Schicht steht unter
`docs/production_10_10/README.md`; die private Owner-Ausrichtung unter
`docs/production_10_10/private_owner_scope.md` und die Main-Console-Richtung
unter `docs/production_10_10/main_console_product_direction.md`.

**Empfohlener erste Live-Stufe — Manual Mirror R1 (operativ, Kurzfassung):**

1. Nur nach erfuellter Shadow-Burn-in-Matrix und archiviertem Bericht (`docs/shadow_burn_in_ramp.md`, ggf. `scripts/verify_shadow_burn_in.py`).
2. ENV: `EXECUTION_MODE=live`, `STRATEGY_EXEC_MODE=manual`, `LIVE_TRADE_ENABLE=true`, `RISK_ALLOWED_LEVERAGE_MAX=7`, `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7` (Obergrenze nur erhoehen, wenn laut Runbook explizit freigegeben).
3. Gates: `LIVE_REQUIRE_EXECUTION_BINDING=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`; nur Kandidaten mit abgestimmtem Shadow/Live-Status laut Katalog/Forensik.
4. Ablauf und Checkboxen: **`docs/LaunchChecklist.md`** (technische [x] = Repostand) + **persoenliches** Management-Signoff in derselben Datei.

## Kernregeln (Betrieb)

- **Ausfuehrung:** drei Modi — **paper** (Referenz), **shadow** (produktionsnaehe ohne echte Orders), **live** (echte Orders nur mit expliziten ENV-Freigaben). Details: `docs/Deploy.md`, `docs/prod_runbook.md`.
- **Owner-Safety-Gates (optional):** Live-Broker kann `MODUL_MATE_GATE_ENFORCEMENT=true` nutzen, um Order-Submits an private Gate-Zeilen in `app.tenant_modul_mate_gates` zu koppeln (historischer Tabellenname; siehe `docs/live_broker.md`, `python tools/modul_mate_selfcheck.py`).
- **Leverage:** nur **Integer 7..75** (konfiguriert als `RISK_ALLOWED_LEVERAGE_MIN` / `RISK_ALLOWED_LEVERAGE_MAX`); mit `RISK_REQUIRE_7X_APPROVAL=true` ohne saubere 7x-Freigabe → **`do_not_trade`**. **Erst-Burn-in:** `RISK_ALLOWED_LEVERAGE_MAX=7` bis Evidenz fuer hoehere Obergrenze (siehe `docs/LaunchChecklist.md`).
- **Stop-Budget:** enge Stops bleiben Kern der Strategie, aber nur innerhalb einer leverage-indexierten Ausfuehrbarkeitskurve. `shared_py.exit_engine.validate_exit_plan(...)` blockiert unhaltbare Kombinationen aus Hebel, Spread, Ticksize, Tiefe und Liquidationspuffer.
- **Produktionsprofil:** keine Fake-/Fixture-Provider-Defaults, kein `pnpm dev` im Produktionscontainer; Secrets nur zur Laufzeit (Vault/KMS/Secret Manager).
- **Sensible APIs:** Gateway mit JWT/internem Key (und optional Legacy nur ausserhalb erzwungener Prod-Auth) — `docs/api_gateway_security.md`.
- **Direkte Service-Zugriffe:** produktionskritische Direktpfade (`llm-orchestrator`, `live-broker`, Admin-/Replay-Pfade der `alert-engine`) sind ueber `INTERNAL_API_KEY` / Header `X-Internal-Service-Key` haertbar; keine ungeschuetzten Produktions-Bypasses.

## Repository Structure

- `apps/`: Dashboard (Next.js `next build` mit **standalone**-Output; Prod-Start `node build/standalone/apps/dashboard/server.js`, siehe `apps/dashboard/package.json`). **Signal-Center** `/signals`: serverseitige Filter (Familie, Playbook, Lane, Regime, Governor/Stop/Exit/Router) via `GET /v1/signals/recent` + Facets `GET /v1/signals/facets`. **Operator-Cockpit** `/ops`: Plan-/Decision-Fenster, Alert-Outbox/Telegram-Spalten, Registry-Slots, Paper-vs-Live-Outcome — nur lesend; keine Strategie-Mutation aus dem Browser.
- `services/`: Microservices (market-stream, engines, paper-broker, **live-broker**, api-gateway, alert-engine, monitor-engine, …).
- `shared/`: TypeScript/Python-Pakete und Vertraege.
- `infra/`: Compose, Migrationen, Prometheus/Grafana (`docs/observability.md`).
- `docs/`: Betrieb, Modell-Stack, Deploy, Runbooks.
- `tests/`: pytest (unit/integration), Dashboard-Jest.

Der zentrale Instrumentenkatalog liegt im Shared-Python-Layer und wird ueber
Bitget-Metadata, Konto-Endpunkte, DB-Snapshots und Redis-Cache gepflegt. Unbekannte
Instrumente fallen auf `no-trade` / `no-subscribe` statt auf stille Defaults.
Ein gemeinsamer Metadatenservice liefert darauf aufbauend Preflight-, Precision-,
Session- und Health-Entscheidungen fuer Orderwege, Exit-Validierung und Operator-Sicht.

## System-Audit (Referenz)

- `docs/REPO_TRUTH_MATRIX.md`, `docs/REPO_FREEZE_GAP_MATRIX.md`, `docs/SYSTEM_AUDIT_MASTER.md` (Verweis, kein eigener Befundtext)
- Zielarchitektur: `docs/adr/ADR-0001-bitget-market-universe-platform.md`

## Tooling Requirements

- Node.js LTS, **pnpm**
- Python **3.11+**
- Docker / Docker Compose (empfohlen fuer Stack und CI-naehe)

## Quickstart (lokal)

**Referenzdoku:** [`docs/LOCAL_START_MINIMUM.md`](docs/LOCAL_START_MINIMUM.md) — Kurzverweis im Root: [`LOCAL_START_MINIMUM.md`](LOCAL_START_MINIMUM.md).

**Standardweg (reproduzierbar, Windows):**

1. `.env.local.example` → `.env.local` und Pflichtwerte setzen.
2. `python tools/validate_env_profile.py --env-file .env.local --profile local`
3. `pip install -r requirements-dev.txt` (u. a. **PyJWT** fuer den Mint-Schritt)
4. `pnpm install`
5. **`pnpm dev:up`** — validiert ENV, **schreibt `DASHBOARD_GATEWAY_AUTHORIZATION`** (JWT), startet `docker-compose.yml`, wartet auf Docker-Healthchecks, oeffnet Browser. Optional: `pnpm dev:up -- -Smoke` (Gateway + Dashboard + Lesepfade). Frische DB: `pnpm dev:up -- -ResetDb`. JWT nicht anfassen: `pnpm dev:up -- -NoMint`.

**Gruen pruefen (nach dem Start):** `pnpm smoke` (wie `pnpm rc:health`) oder `pnpm stack:check`. Bei Gateway-/JWT-Problemen vom Host aus: **`pnpm local:doctor`** (ENV, JWT, `/health`, `/ready`).

**Alternativen:**

- **Gestaffelt + Host-Ports aller Engines:** `pnpm bootstrap:local` / `pwsh scripts/bootstrap_stack.ps1 local` (mintet JWT, `docker-compose.local-publish.yml`).
- **WSL/Linux:** `bash scripts/start_local.sh` → `bootstrap_stack.sh local`.
- **Legacy-Einstieg:** `pnpm stack:local` → `start_local.ps1` (delegiert zu `bootstrap_stack.ps1 local`).

Optional: venv z. B. `services/api-gateway/.venv` fuer Python-CLI.

**Windows (Docker Desktop, PowerShell 5.1+), Details:**

- **Ein Befehl:** `pnpm dev:up` oder `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev_up.ps1`  
  Frische DB: `pnpm dev:up -- -ResetDb` bzw. `... dev_up.ps1 -ResetDb`
- **Weitere Skripte:** `pnpm dev:status`, `pnpm dev:logs`, `pnpm dev:down`, `pnpm dev:reset-db`

Production/Shadow analog: `.env.production.example` bzw. `.env.shadow.example` nach `.env.production` / `.env.shadow`, dann `scripts/start_production.ps1` oder `scripts/start_shadow.ps1`.

**Wichtig bei lokalem Compose:** In `.env.production` / `.env.shadow` muessen die **oeffentlichen** URLs vom Host aus erreichbar sein, sonst schlaegt `scripts/healthcheck.sh` fehl: z. B. `APP_BASE_URL=http://127.0.0.1:8000`, `API_GATEWAY_URL=http://127.0.0.1:8000`, `DASHBOARD_URL=http://127.0.0.1:3000`, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`, `NEXT_PUBLIC_WS_BASE_URL=ws://127.0.0.1:8000`, `FRONTEND_URL`/`CORS_ALLOW_ORIGINS` passend zu `127.0.0.1:3000`. Die Vorlage `.env.production.example` nutzt Platzhalter-Domains ohne `localhost` (Unit-Tests); fuer den echten Start auf einem Rechner anpassen.

Optional: **Git for Windows** (fuer `bash scripts/healthcheck.sh` am Ende des PowerShell-Bootstrap). Ohne Bash: Warnung im Skript; Healthchecks dann manuell ausfuehren.

**ENV-Vorlagen:** `.env.example` (Katalog), `.env.local.example` / `.env.shadow.example` / `.env.production.example` / `.env.test.example`.

Die Profile nutzen dieselbe Kernlogik; Unterschiede liegen in Gates, Secrets und Demo-/Fixture-Verboten. Marktuniversum, Watchlists und Feature-/Signal-Scopes werden jetzt ueber `BITGET_UNIVERSE_*`, `BITGET_WATCHLIST_*`, `FEATURE_SCOPE_*` und `SIGNAL_SCOPE_*` gesteuert.

**Wichtige Doku:**

| Thema                                                     | Datei                                                            |
| --------------------------------------------------------- | ---------------------------------------------------------------- |
| **Launch-Dossier (Freigabeleiter, Cutover, Blocker)**     | **`docs/LAUNCH_DOSSIER.md`**                                     |
| **Launch-Paket (Produktbetrieb, Index)**                  | **`docs/LAUNCH_PACKAGE.md`**                                     |
| Betreiberhandbuch (Single-Host, TLS, Health)              | `docs/OPERATOR_HANDBOOK.md`                                      |
| Externe Go-Live-Abhaengigkeiten                           | `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`                          |
| Private Owner Scope                                       | `docs/production_10_10/private_owner_scope.md`                    |
| Main-Console-Produktdirection                             | `docs/production_10_10/main_console_product_direction.md`         |
| Main-Console-Architektur (Masterplan)                     | `docs/production_10_10/main_console_architecture.md`              |
| Cursor-Arbeitsprotokoll                                   | `docs/production_10_10/cursor_work_protocol.md`                   |
| Legacy-Plaene & Nutzungslogik                             | `docs/PRODUCT_PLANS_AND_USAGE.md`                                |
| CI- & Release-Gates (Merge, Rollback, wöchentlicher Lauf) | `docs/ci_release_gates.md`                                       |
| Deploy & Pflicht-Keys                                     | `docs/Deploy.md`                                                 |
| Bitget-Marktfamilien & Instrumentvertrag                  | `docs/bitget-config.md`                                          |
| Zielarchitektur / Service-Grenzen                         | `docs/adr/ADR-0001-bitget-market-universe-platform.md`           |
| ENV-Profile & Secrets                                     | `docs/env_profiles.md`                                           |
| Pflicht-ENV, Validierung, Fail-fast                       | `docs/CONFIGURATION.md`                                          |
| Go-Live-Checkliste                                        | `docs/LaunchChecklist.md`                                        |
| Shadow-Burn-in & Echtgeld-Ramp                            | `docs/shadow_burn_in_ramp.md`                                    |
| Operator-SOPs & Onboarding                                | `docs/operator_sops.md`, `docs/operator_onboarding_checklist.md` |
| Finaler Readiness-Stand                                   | `docs/FINAL_READINESS_REPORT.md`                                 |
| Evidenz-Scorecard (Schlusspruefung)                       | `docs/FINAL_SCORECARD.md`                                        |
| Release-Bereinigung / Ballast-Log                         | `docs/RELEASE_CLEANUP_REPORT.md`                                 |
| SBOM- / Lockfile-Hinweise                                 | `docs/REPO_SBOM_AND_RELEASE_METADATA.md`                         |
| Tests & Evidenz (Kommandos)                               | `docs/TESTING_AND_EVIDENCE.md`                                   |
| Produktions-Runbook                                       | `docs/prod_runbook.md`                                           |
| Live-Broker                                               | `docs/live_broker.md`                                            |
| Model-Stack v2                                            | `docs/model_stack_v2.md`                                         |
| Playbook-Register                                         | `docs/playbook_registry.md`                                      |
| API-Gateway-Security                                      | `docs/api_gateway_security.md`                                   |
| Operator-Dashboard                                        | `docs/dashboard_operator.md`                                     |
| **Produktstatus (ehrlich)**                               | **`PRODUCT_STATUS.md`**                                          |
| **Release-Readiness (KI-Strecke, Setup, Tests)**          | **`release-readiness.md`**                                       |
| **KI-Architektur (Operator Explain, Konfiguration)**      | **`ai-architecture.md`**                                         |
| **Plan 10/10 Betriebsbereitschaft (10 Schritte)**         | **`docs/PLAN_BETRIEBSBEREIT_10_VON_10.md`**                      |
| **API-/Integrations-Inventar & Smoke**                    | **`API_INTEGRATION_STATUS.md`** (`pnpm api:integration-smoke`)   |
| Observability                                             | `docs/observability.md`                                          |

## Quickstart: Shadow / Production

1. **Go-Live-Reihenfolge:** **`docs/LAUNCH_DOSSIER.md`** (Freigabeleiter); Checkboxen in **`docs/LaunchChecklist.md`** (Secrets → Migrationen → Stack → `scripts/healthcheck.sh` → Tests/Coverage-Gates → Shadow-Burn-in → `RISK_ALLOWED_LEVERAGE_MAX=7` Erstphase → Live-Freigabe).
2. **Secrets:** nur Platzhalter im Repo; echte Werte aus Secret Store.
3. **ENV:** `PRODUCTION=true`, `DEBUG=false`, `LOG_FORMAT=json`, `DATABASE_URL` / `REDIS_URL` und bei Compose `DATABASE_URL_DOCKER` / `REDIS_URL_DOCKER`; Gateway-Auth-Keys siehe `docs/Deploy.md`.
4. **Bootstrap:** `bash scripts/start_shadow.sh` oder `bash scripts/start_production.sh` (optional `WITH_OBSERVABILITY=true`).
5. **Reihenfolge (Compose):** Datastores → Migrationen → Pipeline → Broker & Live-Slot → Alert → Gateway → Monitor → optional Prometheus/Grafana → Dashboard — siehe `scripts/bootstrap_stack.sh` und `docs/Deploy.md`.
6. **Smoke:** `bash scripts/healthcheck.sh` (alle `*_URL` wie im Skript).

**PYTHONPATH (ohne Docker):** Repo-Root + `shared/python/src` fuer `config/` und Shared-Pakete.

## Bitget Demo-Modus mit Demogeld starten

1. Zweck: Demo-Geld-Betrieb nahe an Live, aber ohne Echtgeld.
2. Voraussetzungen: Docker, Docker Compose, lokale Demo-Bitget-Keys, `.env.demo`.
3. Demo-ENV anlegen: `cp .env.demo.example .env.demo`
4. Demo-Readiness pruefen:
   `python scripts/bitget_demo_readiness.py --env-file .env.demo --mode readonly --output-md reports/bitget_demo_readiness.md`
5. Demo-Stack starten: `docker compose --env-file .env.demo up --build`
6. Im Hintergrund starten: `docker compose --env-file .env.demo up --build -d`
7. Main Console: `http://localhost:3000`
8. API-Gateway: `http://localhost:8000`
9. Demo-Healthcheck:
   `python scripts/demo_stack_healthcheck.py --env-file .env.demo --dashboard-url http://localhost:3000 --base-url http://localhost:8000 --output-md reports/demo_stack_healthcheck.md`
10. Demo-Stress-Smoke:
    `python scripts/demo_stress_smoke.py --base-url http://localhost:8000 --dashboard-url http://localhost:3000 --duration-sec 60 --output-md reports/demo_stress_smoke.md`
11. Logs: `docker compose logs -f`
12. Stoppen: `docker compose down`
13. Sicherheitswarnung: Demo nutzt Demogeld; echtes Live-Trading bleibt aus. Demo-Erfolg ist keine Echtgeld-Freigabe.

## Tests & CI

1. `pip install -r requirements-dev.txt` und `pip install -e` wie in `.github/workflows/ci.yml`.
2. **Schnell-Selfcheck:** `pnpm py:selfcheck` bzw. `python tools/production_selfcheck.py` — **Ruff + Black + Mypy** (Risk/Exit, Kommerz-Gates, `model_layer_contract`, wie CI), Modul-Mate-/Policy-/Live-Broker-Gates, `model_layer_contract`, `check_contracts`, Signal-Schema-Fixture, **Prod/Shadow-ENV-Vorlagen-Security**, **synthetisches `local`-Profil aus `.env.local.example`**; wird von `scripts/release_gate.py` zuerst ausgefuehrt. Optional voller Repo-Scan wie CI: `PRODUCTION_SELFCHECK_REPO_SCAN=1` (PowerShell: `$env:PRODUCTION_SELFCHECK_REPO_SCAN='1'`) oder `pnpm py:selfcheck:full` — auf grossen Arbeitskopien kann das laenger dauern.
3. Kurzlauf: `pytest tests shared/python/tests -m "not integration"`.
4. Schema: `python tools/check_schema.py` (siehe `docs/testing_guidelines.md`).
5. Dashboard: `pnpm install --frozen-lockfile` (wie CI) oder `pnpm install`; dann `pnpm --dir apps/dashboard test` und `pnpm --dir apps/dashboard run lint` — Details: `docs/release_build.md`.
6. CI: `.github/workflows/ci.yml`.

## Security Rules

- Keine API-Keys, Tokens oder `.env` mit Secrets committen.
- Rotation bei Leak.
- Frontend nur `NEXT_PUBLIC_*`; Provider- und Exchange-Secrets bleiben serverseitig.
