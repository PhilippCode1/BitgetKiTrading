# Pre-Launch Checkliste und Go-Live-Reihenfolge

**Kanonische Freigabeleiter, Cutover-Stufen, Rollback/Notfall und externe Blocker:** `docs/LAUNCH_DOSSIER.md`.  
**CI-/Release-Gates (Merge, RC, Prod):** `docs/ci_release_gates.md`.  
**Launch-Paket (Index Betrieb, Plaene, externe Abhaengigkeiten):** `docs/LAUNCH_PACKAGE.md`.

Vor Go-Live (**shadow** als Referenz-Betrieb oder **live** mit echten Orders) die Punkte unten abhaken. **Reihenfolge einhalten:** erst Daten und Gates, dann Stack, dann Tests und Burn-in, zuletzt Live-Freigabe.

## Go-Live-Reihenfolge (verbindlich)

1. **Secrets** aus Secret Manager / Vault injizieren — kein Commit von `.env` mit echten Werten; Rotation bei Leck.
2. **Profil** waehlen: Shadow- oder Produktions-ENV laut `docs/Deploy.md` / `.env.shadow.example` bzw. `.env.production.example` — keine Demo-/Fixture-/Fake-Provider-Defaults in diesen Profilen.
3. **Postgres + Redis** erreichbar; **Migrationen:** `python infra/migrate.py` mit gueltiger `DATABASE_URL` (siehe `infra/migrate.py`).
4. **Compose oder Bootstrap:** `docker compose up -d --build` (mit `COMPOSE_ENV_FILE` auf die gewaehlte ENV-Datei) oder `bash scripts/start_shadow.sh` / `bash scripts/start_production.sh` — siehe `docker-compose.yml`, `scripts/bootstrap_stack.sh`.
5. **Healthchecks:** alle `*_URL` wie in `scripts/healthcheck.sh` setzen, dann `bash scripts/healthcheck.sh` bis gruen; Gateway-Aggregat prueft u. a. DB, Redis, Service-`ready`, Ops-Summary (Monitor, Alert-Engine, Live-Broker).
6. **Tests (Release-Gate):** lokal oder CI-aequivalent (`docs/ci_release_gates.md`):
   - `coverage run -m pytest tests shared/python/tests -m "not integration"` und `python tools/check_coverage_gates.py`
   - `pytest tests/integration tests/learning_engine -m integration` mit `TEST_DATABASE_URL` / `TEST_REDIS_URL` (HTTP-Stack-Tests nur mit echtem Stack + `API_GATEWAY_URL` / JWT)
   - Schema: `python tools/check_schema.py` (Fixtures unter `tests/fixtures/`)
   - Dashboard: `pnpm install --frozen-lockfile` und `pnpm --dir apps/dashboard run lint` sowie `pnpm --dir apps/dashboard test`
   - **Compose-Stack (wie CI):** nach gruenem `scripts/healthcheck.sh` nacheinander `python scripts/rc_health_runner.py .env.local` und `python scripts/verify_ai_operator_explain.py --env-file .env.local --mode orchestrator` (Dashboard-Health, Gateway-Kernpfade, **KI mit Fake-Provider**)
7. **Replay-Determinismus:** deterministische Pfade in Shared/Risk/Exit/Paper/Live-Execution per Tests abgedeckt (`tests/`, `shared/python/tests/`); vollstaendige Bit-fuer-Bit-Replay des **gesamten** Stacks inkl. LLM-Orchestrator ist **nicht** als abgeschlossen dokumentiert (`docs/REPO_FREEZE_GAP_MATRIX.md` — u. a. Backoff mit Zufall im LLM-Service). Fuer Go-Live: Trading-Kern = deterministische Safety-Layer + quant/ML + Risk + Uncertainty + Gating; LLM nur unterstuetzend.
8. **Shadow-Burn-in:** zuerst `EXECUTION_MODE=shadow`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false`, `LIVE_BROKER_ENABLED=true`, `LIVE_REQUIRE_EXECUTION_BINDING=true`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`; Burn-in-Kohorten und Kriterien laut `docs/shadow_burn_in_ramp.md`.
9. **Konservative Erstfreigabe Hebel:** fuer die erste Echtgeldstufe bleiben **`RISK_ALLOWED_LEVERAGE_MAX=7`** und **`RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`** gesetzt. Erhoehung nur nach dokumentierter Evidenz, nicht aus Marketing-Gruenden.
10. **Live-Mirror-Freigabe** erst nach Shadow-Burn-in: `EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true`, `STRATEGY_EXEC_MODE=manual`, Live-Broker enabled, Bitget-Keys und Passphrase nur zur Laufzeit; nur `candidate_for_live` + `live_mirror_eligible=true` + `shadow_live_match_ok=true`.

## Secrets und Profile

- [ ] Keine `.env` mit echten Secrets im Git; Rotation bei Leck.
- [ ] Profil gewaehlt: **local** (nur Entwicklung), **shadow** oder **production** laut `docs/Deploy.md` — **keine** Demo-/Fixture-/Fake-Defaults in shadow/production.
- [ ] `PRODUCTION=true` fuer shadow/prod-Hosts; `DEBUG=false`, `LOG_LEVEL` nicht `DEBUG`, `LOG_FORMAT=json`.

## Daten und Migrationen

- [ ] `DATABASE_URL`, `REDIS_URL` aus Secret Manager; bei Compose zusaetzlich `DATABASE_URL_DOCKER`, `REDIS_URL_DOCKER`.
- [ ] Migrationen angewendet (`infra/migrate.py`); Backup-Strategie fuer Postgres dokumentiert.

## Ausfuehrungsmodus und Risk

- [ ] **paper** / **shadow** / **live** bewusst gesetzt: `EXECUTION_MODE`, `SHADOW_TRADE_ENABLE`, `LIVE_TRADE_ENABLE` konsistent mit Ziel (`docs/Deploy.md`, `docs/live_broker.md`).
- [ ] **Live-Orders** nur mit `EXECUTION_MODE=live` **und** `LIVE_TRADE_ENABLE=true` **und** freigegebenem Live-Broker-Slot.
- [ ] `RISK_HARD_GATING_ENABLED=true`, `RISK_ALLOWED_LEVERAGE_MIN=7`, `RISK_ALLOWED_LEVERAGE_MAX` im Bereich **7..75**, `RISK_REQUIRE_7X_APPROVAL=true`, `RISK_DEFAULT_ACTION=do_not_trade` — ohne saubere 7x-Freigabe kein Trade.
- [ ] Burn-in-Profil bewusst geprueft: `RISK_ALLOWED_LEVERAGE_MAX=7` bleibt im Profil und in der Freigabekette gesetzt, bis eine spaetere Erhoehung explizit genehmigt ist.
- [ ] `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7` fuer die Startstufe gesetzt.

## Gateway, Auth, Kill-Switch, Drift

- [ ] Gateway: `GATEWAY_JWT_SECRET` und/oder `GATEWAY_INTERNAL_API_KEY`; `GATEWAY_ENFORCE_SENSITIVE_AUTH` in Prod wie gewuenscht (`docs/api_gateway_security.md`).
- [ ] `CORS_ALLOW_ORIGINS` auf echte Frontend-Origins.
- [ ] Dashboard Prod: `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true` und serverseitig `DASHBOARD_GATEWAY_AUTHORIZATION` gesetzt (`docs/dashboard_operator.md`).
- [ ] `ADMIN_TOKEN` nur noch relevant, wenn Legacy-Admin ohne erzwungenes Gateway-Auth (typisch **nicht** fuer harten Prod-Proxy-Modus).
- [ ] Kill-Switch: bei aktivem Switch Alerts und Live-Broker-Ops pruefen; Resume nur mit Freigabe (`docs/prod_runbook.md`).
- [ ] Drift-/Registry: harte Bloecke und Champion-Policy laut `docs/model_registry_v2.md` / Learning-Config verstanden; keine Promotion ohne Gates.
- [ ] `LIVE_REQUIRE_EXECUTION_BINDING=true`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`.
- [ ] Approval Queue, Live Mirrors und `/live-broker/forensic/[id]` im Operator-Cockpit fuer die Startkohorte geprueft.

## Shadow-Burn-in und Echtgeld-Ramp

- [ ] Repraesentative Burn-in-Matrix ueber reale Marktfamilien / Instrumenttypen / Regime / Spezialistenrouten laut `docs/shadow_burn_in_ramp.md` abgeschlossen.
- [ ] Data Health, Route Stability, No-Trade Quality, Stop Fragility, Shadow-Live Divergence, Reconcile Cleanliness und Incident-Free Runtime gleichzeitig gruen.
- [ ] Operator-Readiness-Drill absolviert: Release, Kill-Switch, Safety-Latch, Emergency-Flatten, Forensik.
- [ ] Startkohorte fuer Echtgeld-Mirror explizit dokumentiert: Familie, Symbole, Playbook-Familien, Hebelstufe.
- [ ] No-Go-/Fallback-Bedingungen definiert; bei Verstoß faellt der Stack wieder auf `shadow-only`.

## Compose und Smoke

- [ ] Stack-Start gruen; `bash scripts/healthcheck.sh` OK (alle `*_URL` gesetzt).
- [ ] Optional: Observability `WITH_OBSERVABILITY=true` — Prometheus **9090**, Grafana **3001** (`docs/observability.md`).

## Rechtliches

- [ ] DSGVO/MiCA falls personenbezogene oder marktrelevante Daten.

## Nach Deploy

- [ ] Fehlerrate in Logs (ohne Secrets in Zeilen).
- [ ] Rollback-Image-Tag / Compose-Revision notiert.
- [ ] Stichprobe: `GET /v1/system/health`; bei Bedarf Operator-Cockpit `/ops`.
