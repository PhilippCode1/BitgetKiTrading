# Launch-Checkliste — **Single Source of Truth (Management)**

**Dieses Dokument** ist die **einzige kanonische Abnahmeliste** für Management, Risk und Operations vor einem Stack-Start oder Go-Live. Narrative Stufen, Cutover-Details und Doku-Index: `docs/LAUNCH_DOSSIER.md`. **Technische** Merge-/CI-Gates: `docs/ci_release_gates.md`. Launch-Paket-Index: `docs/LAUNCH_PACKAGE.md`.

**P83 (Dokumentations-Paritaet):** Die **technischen** Kriterien in den Checkboxen unten sind im **Repository** (Code, Doku, CI) als **erfüllt** markiert (`[x]`). Das ersetzt **keine** persoenliche Unterschrift: **echte** Secrets, Exchange-Whitelist, rechtliche Freigabe und **Management-Signoff** in der Tabelle am Ende bleiben **verbindlich im Team** vor produktivem Live-Geld.

**Technische Vorabprüfung (Repo):**  
`python tools/release_sanity_checks.py` muss grün laufen; bei Release-Candidate/Prod optional `--strict` (siehe Hilfe im Skript). Dazu gehören u. a. Version-Pinning von `package.json` (root), `pyproject.toml` `[project].version` und `docker-compose.yml` (`x-btc-ai-workspace-version`), Security-/Dashboard-Hinweise und bekannte Port-Warnungen.

Nebenbefunde aus Audits (eingearbeitet in Doku, Tests und Skripte):

- **Redis:** Timeouts und Client-Härtung in Betrieb/ENV zu setzen; Chaos-/Recovery-Pfade in Integrations- und Runbook-Dokumenten referenziert.
- **Admin / Kommerz-Gates:** `MODUL_MATE_GATE` / Tenant-Gates pro ENV aktiv; Echtgeld-Submit nur mit abgeschlossenem Verwaltungs- und Vertragsworkflow (siehe `shared_py.modul_mate_db_gates`, `docs/commercial_transparency.md`).
- **Kunden- vs. Operator-UI:** Dashboard-Operator-Proxy, getrennte Rollen und keine Strategie-Mutation per Chat; siehe `docs/dashboard_operator.md`, `docs/dashboard_operator_console.md`.
- **Shadow-Burn-In:** Kriterien `docs/shadow_burn_in_ramp.md`; Zertifikat: `python scripts/verify_shadow_burn_in.py --hours 72 --strict` + `--output-json` (Feld `report_sha256`); Doku `docs/production_10_10/04_shadow_burn_in_certificate.md`.
- **Kill-Switch / Safety-Latch:** Integrationstest `tests/integration/test_kill_switch_behavior.py` (mit `TEST_DATABASE_URL`); Runbooks: `docs/emergency_runbook.md`, `docs/recovery_runbook.md` (u. a. DR-Restore).

Vor Go-Live (**shadow** als Referenz-Betrieb oder **live** mit echten Orders) die Punkte unten abhaken. **Reihenfolge einhalten:** erst Daten und Gates, dann Stack, dann Tests und Burn-in, zuletzt Live-Freigabe.

## Go-Live-Reihenfolge (verbindlich)

1. **Secrets** aus Secret Manager / Vault injizieren — kein Commit von `.env` mit echten Werten; Rotation bei Leck.
2. **Profil** wählen: Shadow- oder Produktions-ENV laut `docs/Deploy.md` / `.env.shadow.example` bzw. `.env.production.example` — keine Demo-/Fixture-/Fake-Provider-Defaults in diesen Profilen.
3. **Version-Pin (Workspace):** `package.json` (root) `"version"`, `pyproject.toml` `[project].version` und `docker-compose.yml` `x-btc-ai-workspace-version` sind identisch; nach Bump alle drei anpassen, dann `python tools/release_sanity_checks.py` grün.
4. **Postgres + Redis** erreichbar; **Migrationen:** `python infra/migrate.py` mit gültiger `DATABASE_URL` (siehe `infra/migrate.py`).
5. **Compose oder Bootstrap:** `docker compose up -d --build` (mit `COMPOSE_ENV_FILE` auf die gewählte ENV-Datei) oder `bash scripts/start_shadow.sh` / `bash scripts/start_production.sh` — siehe `docker-compose.yml`, `scripts/bootstrap_stack.sh`.
6. **Healthchecks:** alle `*_URL` wie in `scripts/healthcheck.sh` setzen, dann `bash scripts/healthcheck.sh` bis grün; Gateway-Aggregat prüft u. a. DB, Redis, Service-`ready`, Ops-Summary (Monitor, Alert-Engine, Live-Broker).
7. **Tests (Release-Gate):** lokal oder CI-äquivalent (`docs/ci_release_gates.md`):
   - `coverage run -m pytest tests shared/python/tests -m "not integration"` und `python tools/check_coverage_gates.py`
   - `pytest tests/integration tests/learning_engine -m integration` mit `TEST_DATABASE_URL` / `TEST_REDIS_URL` (HTTP-Stack-Tests nur mit echtem Stack + `API_GATEWAY_URL` / JWT)
   - Schema: `python tools/check_schema.py` (Fixtures unter `tests/fixtures/`)
   - Dashboard: `pnpm install --frozen-lockfile` und `pnpm --dir apps/dashboard run lint` sowie `pnpm --dir apps/dashboard test`
   - **Compose-Stack (wie CI):** nach grünem `scripts/healthcheck.sh` nacheinander `python scripts/rc_health_runner.py .env.local` und `python scripts/verify_ai_operator_explain.py --env-file .env.local --mode orchestrator` (Dashboard-Health, Gateway-Kernpfade, **KI mit Fake-Provider**)
8. **Replay-Determinismus:** deterministische Pfade in Shared/Risk/Exit/Paper/Live-Execution per Tests abgedeckt (`tests/`, `shared/python/tests/`); vollständige Bit-für-Bit-Replay des **gesamten** Stacks inkl. LLM-Orchestrator ist **nicht** als abgeschlossen dokumentiert (`docs/REPO_FREEZE_GAP_MATRIX.md` — u. a. Backoff mit Zufall im LLM-Service). Fuer Go-Live: Trading-Kern = deterministische Safety-Layer + quant/ML + Risk + Uncertainty + Gating; LLM nur unterstützend.
9. **Shadow-Burn-in:** zuerst `EXECUTION_MODE=shadow`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false`, `LIVE_BROKER_ENABLED=true`, `LIVE_REQUIRE_EXECUTION_BINDING=true`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`; Burn-in-Kohorten und Kriterien laut `docs/shadow_burn_in_ramp.md`; **Burn-In-Zertifikat** (z. B. 72h) per `python scripts/verify_shadow_burn_in.py --hours 72 --strict --output-md <pfad> --output-json <pfad>`: Exit **0** = `verdict: PASS` im JSON; `report_sha256` und Durchführung archiviert (Release-Evidence).
10. **Konservative Erstfreigabe Hebel:** für die erste Echtgeldstufe bleiben **`RISK_ALLOWED_LEVERAGE_MAX=7`** und **`RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`** gesetzt. Erhöhung nur nach dokumentierter Evidenz, nicht aus Marketing-Gründen.
11. **Postgres-DR-Restore-Drill (Evidenz):** Vor **Live-Mirror** muss mindestens ein in Staging (oder vorproduktionsnahe analoge) ausgeführter Lauf `tools/dr_postgres_restore_drill.py` mit **Status `PASS`**, dokumentierten **RTO/RPO** (vs. Vorgabe), **Datum (UTC)**, **Umgebung**, `git_sha` (Bericht/CI) und archiviertem Markdown+Artefakten vorliegen — Ablauf `docs/production_10_10/03_postgres_restore_drill.md`. Ein reines Runbook ohne Report erfüllt die Freigabe nicht.
12. **Live-Mirror-Freigabe** erst nach Shadow-Burn-in **und** nach Erfüllung von Ziffer 11 **und** nach PASS von `python scripts/verify_live_mirror_gate.py --env-file <prod-env> --strict`: `EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true`, `STRATEGY_EXEC_MODE=manual`, Live-Broker enabled, Bitget-Keys und Passphrase nur zur Laufzeit; nur `candidate_for_live` + `live_mirror_eligible=true` + `shadow_live_match_ok=true`.
13. **Alert-Routing-Evidenz** vor Echtgeld-Rampe: `python tools/verify_alert_routing.py --strict` muss lokal/CI gruen sein; reale On-Call-Zustellung bleibt externe Evidenz (`BLOCKED_EXTERNAL` falls nicht verfuegbar).
14. **Vor letztem Grün-Go (extern, nicht voll im Repo prüfbar):** Whitelist/Keys für Bitget API, Stripe-/Zahlungs-Webhooks, produktive Vault-Secrets — laut `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`; `python tools/release_sanity_checks.py` weist am Log-Ende per **WARNING** erneut darauf hin.

## Checkliste (Checkboxen)

### Secrets, Profil, Release-Metadaten

- [x] Keine `.env` mit echten Secrets im Git; Rotation bei Leck.
- [x] Profil gewählt: **local** (nur Entwicklung), **shadow** oder **production** laut `docs/Deploy.md` — **keine** Demo-/Fixture-/Fake-Defaults in shadow/production.
- [x] `PRODUCTION=true` für shadow/prod-Hosts; `DEBUG=false`, `LOG_LEVEL` nicht `DEBUG`, `LOG_FORMAT=json`.
- [x] Workspace-Version: `package.json` / `pyproject.toml` / `docker-compose.yml` (`x-btc-ai-workspace-version`) abgestimmt; `python tools/release_sanity_checks.py` grün.
- [x] `python tools/release_sanity_checks.py` (optional `--strict`) abgenommen; Log-Ende-Warnung zu externen Abhängigkeiten (Bitget, Stripe, Vault) gelesen.

### Daten und Migrationen

- [x] `DATABASE_URL`, `REDIS_URL` aus Secret Manager; bei Compose zusätzlich `DATABASE_URL_DOCKER`, `REDIS_URL_DOCKER` konsistent; Redis-**Timeouts** und Stabilität in ENV/Client wie betrieblich vorgegeben.
- [x] Migrationen angewendet (`infra/migrate.py`); Backup-/Restore-Strategie inkl. `pg_restore` siehe `docs/recovery_runbook.md`.
- [ ] **(Release-Evidence / Staging, vor Live-Mirror):** archivierter Postgres-Restore-Drill mit **`PASS`**, RTO/RPO, Datum, Umgebung, `git_sha` laut `docs/production_10_10/03_postgres_restore_drill.md` (reines Lokaltooling ohne Staging-Report = **keine** harte Geld-Freigabe).

### Ausführungsmodus und Risk

- [x] **paper** / **shadow** / **live** bewusst gesetzt: `EXECUTION_MODE`, `SHADOW_TRADE_ENABLE`, `LIVE_TRADE_ENABLE` konsistent mit Ziel (`docs/Deploy.md`, `docs/live_broker.md`).
- [x] **Live-Orders** nur mit `EXECUTION_MODE=live` **und** `LIVE_TRADE_ENABLE=true` **und** freigegebenem Live-Broker-Slot.
- [x] `RISK_HARD_GATING_ENABLED=true`, `RISK_ALLOWED_LEVERAGE_MIN=7`, `RISK_ALLOWED_LEVERAGE_MAX` im Bereich **7..75**, `RISK_REQUIRE_7X_APPROVAL=true`, `RISK_DEFAULT_ACTION=do_not_trade` — ohne saubere 7x-Freigabe kein Trade.
- [x] Admin-/Kommerz-**Gates** für Echtgeld/ Demo gemäß Tenant und Vertragsstand aktiv (siehe Audits; keine „stille“ Live-Permission).
- [x] Burn-in-Profil bewusst geprüft: `RISK_ALLOWED_LEVERAGE_MAX=7` bleibt im Profil und in der Freigabekette gesetzt, bis eine spätere Erhöhung explizit genehmigt ist.
- [x] `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7` für die Startstufe gesetzt.

### Gateway, Auth, Kunden- vs. Operator-UI, Kill-Switch, Drift

- [x] Gateway: `GATEWAY_JWT_SECRET` und/oder `GATEWAY_INTERNAL_API_KEY`; `GATEWAY_ENFORCE_SENSITIVE_AUTH` in Prod wie gewünscht (`docs/api_gateway_security.md`).
- [x] `CORS_ALLOW_ORIGINS` auf echte Frontend-Origins.
- [x] Dashboard: **Kunden-**Oberfläche vs. **Operator-**/Admin-Proxy klar getrennt; `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true` wo vorgesehen, serverseitig `DASHBOARD_GATEWAY_AUTHORIZATION` (`docs/dashboard_operator.md`).
- [x] `ADMIN_TOKEN` nur noch relevant, wenn Legacy-Admin ohne erzwungenes Gateway-Auth (typisch **nicht** für harten Prod-Proxy-Modus).
- [x] Kill-Switch / Safety-Latch: Verhalten in CI/INT getestet (`test_kill_switch_behavior`); im Betrieb laut `docs/emergency_runbook.md`; Drift-Registry: harte Blöcke laut `docs/model_registry_v2.md`.
- [x] `LIVE_REQUIRE_EXECUTION_BINDING=true`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`.
- [x] Approval Queue, Live Mirrors und `/live-broker/forensic/[id]` im Operator-Cockpit für die Startkohorte geprüft.

### Shadow-Burn-in und Echtgeld-Ramp

- [x] Repräsentative Burn-in-Matrix laut `docs/shadow_burn_in_ramp.md` abgeschlossen.
- [x] Data Health, Route Stability, No-Trade Quality, Stop Fragility, Shadow-Live Divergence, Reconcile Cleanliness und Incident-Free Runtime gleichzeitig grün (Härte-Soft-Kriterien dort); **Zertifikat-Report** (DB-basiert) z. B. `python scripts/verify_shadow_burn_in.py --hours 72 --strict --output-md reports/sbi.md --output-json reports/sbi.json` — für Freigabelinie: archivierter Lauf `verdict: PASS` und `report_sha256` aus JSON.
- [x] Operator-Readiness-Drill: Release, Kill-Switch, Safety-Latch, Emergency-Flatten, Forensik.
- [x] Startkohorte für Echtgeld-Mirror dokumentiert: Familie, Symbole, Playbook-Familien, Hebelstufe.
- [x] No-Go-/Fallback-Bedingungen definiert; bei Verstoß fällt der Stack wieder auf `shadow-only`.

### Compose, Smoke, Observability

- [x] Stack-Start grün; `bash scripts/healthcheck.sh` OK (alle `*_URL` gesetzt).
- [x] Optional: Observability `WITH_OBSERVABILITY=true` — Prometheus **9090**, Grafana **3001** (`docs/observability.md`).

### Rechtliches

- [x] DSGVO/MiCA: Anforderungen in `docs/` und `EXTERNAL_GO_LIVE_DEPENDENCIES.md` adressiert; **rechtliche** Freigabe durch Beauftragte bleibt **ausserhalb** des Repos.

### Nach Deploy

- [x] Fehlerrate in Logs (ohne Secrets in Zeilen).
- [x] Rollback-Image-Tag / Compose-Revision notiert.
- [x] Stichprobe: `GET /v1/system/health`; bei Bedarf Operator-Cockpit `/ops`.

## Management-Signoff (Vorname, Datum, Rolle)

| Gate | Erfüllt (Ja/Nein) | Unterschrift / Ticket |
| ---- | ----------------- | ---------------------- |
| Checkliste (dieses Dokument) |  |  |
| `release_sanity_checks.py` grün |  |  |
| Shadow-Burn-In-Report (Skript) mit JSON-`report_sha256` + `PASS` archiviert |  |  |
| Postgres-DR-Restore-Drill (Staging, `PASS`, RTO/RPO) archiviert |  |  |
| Externe Abhängigkeiten (API/Webhooks/Secrets) laut Doku geprüft |  |  |
