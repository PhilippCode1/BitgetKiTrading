# CI- und Release-Gates (Merge, Release-Candidate, Production)

Ergänzung zu **`docs/LAUNCH_DOSSIER.md`** (Freigabeleiter). Technische Details: **`.github/workflows/ci.yml`**, **`tools/check_coverage_gates.py`**.

## Branch-Policy (main deploybar)

- **Push-CI** läuft nur auf **`main`** und **`master`** (kein automatischer CI-Push auf beliebige Feature-Branches) — Qualität kommt über **PRs** in den geschützten Branch.
- Im GitHub-Repo unter **Settings → Branches → Branch protection** für `main` (und ggf. `master`) mindestens aktivieren:
  - **Require a pull request before merging** (kein ungeprüfter Direktpush in den Normalfall; Admin-Umgehung ist organisationsspezifisch und separat prüfbar).
  - **Require status checks** vor dem Merge: exakt die Jobs aus `.github/workflows/ci.yml` (Workflow-Name: `ci`), sichtbar als:
    - `ci / python` — *Python (Ruff, pytest, …)*
    - `ci / dashboard` — *Dashboard (types, Jest, build, pnpm audit)*
    - `ci / compose_healthcheck` — *Docker Compose + Health + KI-Smoke + Playwright E2E*
    - `ci / release-approval-gate` — *Unified Release Gate (all jobs + FREEZE + version lock)* (zieht `tools/check_release_approval_gates.py` + Freeze-Matrix; **für abgesichertes Merging zwingend**).
  - **Force-Disallow:** Force-Pushes in den Regeln verbieten, soweit Policy; **Löschungen** abwehren, soweit nicht explizit erforderlich.
  - Optional: **Require branches to be up to date** vor dem Merge; optional **Enforce** für Admins, wenn eure Orga das dulden kann (sonst: Eskalation über Org-Owner, nicht im Repo-allein sichtbar).
- **Wöchentlicher Lauf:** Workflow `ci` per `schedule` (Montag 05:00 UTC) führt **`python`** und **`dashboard`** aus — **ohne** Docker-Compose-Job (Kosten/Laufzeit). Vollstack weiterhin bei jedem PR/Push auf `main`.

### Werkzeug: `tools/check_github_branch_protection.py`

- **Zweck:** Gegenprüfung, ob laut GitHub-API (oder **Offline-Fixture** in Tests) die erforderlichen Status-Checks inkl. **`release-approval-gate`** erfasst werden und PR-/Force-Policy-Teile lesbar sind.
- **Ohne** `GITHUB_TOKEN` / `GH_TOKEN` / `gh` mit Berechtigung: kein `PASS` — `UNKNOWN_NO_GITHUB_AUTH` (Evidenz bleibt **extern / BLOCKED** bis zum laufenden `read_scope`-Token im CI oder einem Admin-Run).
- **Befehle (Beispiele):**
  - Lokal mit Leserechten (Repo: Standard `GITHUB_REPOSITORY` aus der Umgebung, sonst `--repo owner/name`):
    - `python tools/check_github_branch_protection.py --repo PhilippCode1/BitgetKiTrading --branch main`
  - Strikter Go-/Abnahmecheck: `--strict` → **Exit-Code 1** bei alles, was kein `PASS` ist (inkl. `UNKNOWN*`), damit **Echtgeld-Go** nicht fälschlich belegt ist.
  - **Offline-Tests/Regression:** `pytest tests/unit/tools/test_check_github_branch_protection.py -q`
- **Evidenz für 10/10-Map (Evidenz, nicht Doku-Claim):** Screenshot/Export aus GitHub **und** mindestens eine Lauf-JSON-Ausgabe des Werkzeugs:  
  `python tools/check_github_branch_protection.py --repo <owner>/<repo> --branch main --json docs/release_evidence/branch_protection_YYYYMMDD.json` (nach erfolgreichem `PASS`; bei `UNKNOWN` nur als **Hinweis-Blocker**, in `docs/production_10_10/...` kennzeichnen), optional `--report-md` für die gleiche Sitzung.
- **Hinweis:** Der CI-Job-Step „Branch-Protection-Tool (informativ)“ ist **non-blocking** (`continue-on-error: true`); der Standard-`GITHUB_TOKEN` in Actions liefert oft **403/UNKNOWN** auf den Protection-Read — Ergebnis wird geloggt, **echter** L4/L5-Nachweis bleibt `BLOCKED_EXTERNAL` bis ein Admin-Token/Org-Export o. a. vorgelegt wird.

## Merge (jedes PR / Push auf geschützte Branches)

| Gate                                      | Beschreibung                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Shell                                     | `bash -n` auf `scripts/start_all.sh`, `healthcheck.sh`, `deploy.sh`, `integration_compose_smoke.sh`, `rc_health.sh`                                                                                                                                                                                                                                                                                                                                                                                    |
| Release-Sanity                            | `python tools/release_sanity_checks.py` — offensichtliche Secrets, übergroße Text-Artefakte, riskante `0.0.0.0`-Port-Zeilen in `docker-compose.yml`                                                                                                                                                                                                                                                                                                                                                    |
| ENV-Vorlagen (Security)                   | `python tools/check_production_env_template_security.py` — `.env.production.example` / `.env.shadow.example` ohne aktive Debug-/Demo-/Auth-offene Flags                                                                                                                                                                                                                                                                                                                                                |
| Lint                                      | Ruff auf `tests/**`, `tools/check_schema.py`, `tools/check_coverage_gates.py`, `tools/release_sanity_checks.py`, Integration inkl. `fixtures`                                                                                                                                                                                                                                                                                                                                                          |
| Format                                    | Black (ohne `tests/unit` — Legacy)                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Typprüfung                                | Mypy in `shared/python` auf: `leverage_allocator`, `risk_engine`, `exit_engine`, `shadow_live_divergence`                                                                                                                                                                                                                                                                                                                                                                                              |
| Packaging-Smoke                           | `python -m build shared/python --wheel` + Wheel-Inhaltsprüfung                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Schema                                    | `tools/check_schema.py` mit Fixture-JSON                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| DB                                        | `infra/migrate.py` gegen CI-Postgres                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Tests + Coverage                          | `coverage run` Unit; `coverage run -a` Integration; dann `check_coverage_gates.py` + `coverage xml`                                                                                                                                                                                                                                                                                                                                                                                                    |
| Supply-Chain (blocking)                   | Python: `python tools/pip_audit_supply_chain_gate.py` (`requirements-dev.txt` + `constraints-runtime.txt`, CVSS/OSV HIGH+ mit Allowlist `tools/pip_audit_allowlist.txt`); Dashboard-Job: `pnpm audit --audit-level=high`                                                                                                                                                                                                                                                                               |
| Dashboard                                 | `pnpm install --frozen-lockfile`, lint, `test:ci` mit Coverage, Build                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Compose + Smoke + **KI** + **Playwright** | `docker compose … config --quiet`; Build+Up; `healthcheck.sh` mit Retries; **`python3 scripts/rc_health_runner.py .env.local`** (wie **`pnpm smoke`**); **`python3 scripts/verify_ai_operator_explain.py --env-file .env.local --mode orchestrator`** (Fake-Provider aus CI-`.env.local`); danach **`pnpm exec playwright test -c e2e/playwright.config.ts`** gegen **Dashboard :3000** — prüft u. a. Startseite, Konsole, **Terminal/Chart**, **BFF Operator-Explain**, Broker-Seite, Kernnavigation. |

## Coverage-Schwellen (nach vollem Testlauf)

| Metrik                                        | Minimum                                                                                                         |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `shared_py` (Gesamtpaket, Branch-Report)      | 80 %                                                                                                            |
| `live_broker` (Gesamtpaket)                   | 62 %                                                                                                            |
| Kritische Kernmodule (aggregiert, Zeilen)     | 90 % — Dateiliste in `check_coverage_gates.py` (`CRITICAL_SUFFIXES`), inkl. Forensik-/Auth-/Operator-Intel-Kern |
| High-Risk-Bündel (REST, Reconcile, Divergenz) | 81 % — `HIGH_RISK_SUFFIXES`                                                                                     |

Zusaetzlich: globales `fail_under = 25` in `pyproject.toml` / `.coveragerc` (kein triviales 0 %-Grün bei `coverage report` allein).

## Release-Candidate (empfohlen zusätzlich)

| Maßnahme                | Befehl / Ort                                                                                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Gebündelter RC-Lauf     | `bash scripts/release_candidate.sh`                                                                                                                    |
| Striktere Sanity        | `python tools/release_sanity_checks.py --strict` (WARN → Fehler)                                                                                       |
| pip-audit ohne Toleranz | `python tools/pip_audit_supply_chain_gate.py` (Dev + Runtime-Constraints) — Policy „Fix oder Eintrag in `tools/pip_audit_allowlist.txt` dokumentieren“ |
| Manuelle Stack-Smokes   | `API_GATEWAY_URL`, JWT, optional `INTEGRATION_SAFETY_MUTATIONS=1` — siehe `docs/integration_full_stack_scenarios.md`                                   |

## Production (organisatorisch)

- Alle Punkte aus **`docs/LaunchChecklist.md`** und Stufe G5 in **`docs/LAUNCH_DOSSIER.md`**.
- Keine Abweichung von `docs/env_profiles.md` für `PRODUCTION=true`.
- On-Call, Backup-Nachweis und Incident-Kette außerhalb des Repos verbindlich machen.

---

## Freigabe (Release) — Ablauf in klaren Schritten

1. **Grün auf main:** Alle erforderlichen CI-Checks grün; kein Merge ohne grüne `python` / `dashboard` / `compose_healthcheck`.
2. **ENV / Profil:** Zielumgebung mit `docs/env_profiles.md` und `STAGING_PARITY.md` abgleichen; Secrets nicht im Repo.
3. **Smoke vor Deploy:** In der Zielumgebung `scripts/staging_smoke.py` oder `pnpm smoke` / `rc_health_runner` gegen die **tatsächlichen** URLs (nicht nur lokale `.env.local`).
4. **Deploy:** Image-Tag / Revision dokumentieren (Git SHA, Build-Nummer).
5. **Post-Deploy:** `GET /ready` am Gateway, Stichprobe `GET /v1/system/health` mit gültigem JWT; siehe `OBSERVABILITY_AND_SLOS.md`.

## Rollback — Ablauf in klaren Schritten

1. **Symptom festhalten:** Zeitpunkt, betroffene Route(n), Request-IDs aus Logs (`OBSERVABILITY_AND_SLOS.md`).
2. **Schnell-Rollback:** Vorheriges bekanntes gutes **Image-Tag** / **Revision** erneut ausrollen (Compose/Kubernetes — je nach Infrastruktur).
3. **Konfiguration:** Bei Fehlkonfiguration statt Codefehler: letzte gültige **ENV-/Secret-Version** aus Secret-Store zurücksetzen, Dienst neu starten.
4. **Datenbank:** Nur bei explizitem Migrations-Rollback-Plan (vorwärts-kompatible Migrationen bevorzugen); nicht „aus dem Bauch“ `migrate down` in Produktion.
5. **Kommunikation:** Status an Betrieb/Stakeholder; nach Stabilisierung Postmortem kurz dokumentieren.

---

## Referenz: zentrale Nutzer-/Stack-Smokes

| Skript / Kommando                       | Zweck                                                                                                                                                                                 |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/release_gate.py`               | Gebündelt: `api_integration_smoke`, optional `rc_health_runner` + `verify_ai_operator_explain`, `dashboard_page_probe`, optional Playwright (`--with-e2e` / `pnpm release:gate:full`) |
| `scripts/rc_health_runner.py`           | Dashboard `/api/health`, Gateway `/ready`, `/v1/system/health`, mehrere Lesepfade                                                                                                     |
| `scripts/verify_ai_operator_explain.py` | KI: Orchestrator direkt oder über Gateway                                                                                                                                             |
| `scripts/dashboard_page_probe.py`       | HTTP-HTML auf Kernrouten (inkl. `/`, `/console`, Broker; Terminal bewusst ohne — client-heavy)                                                                                        |
| `e2e/tests/release-gate.spec.ts`        | Playwright: Chart, KI-BFF, Navigation (laufendes Dashboard nötig)                                                                                                                     |
| `scripts/staging_smoke.py`              | Staging: Health + System-Health + KI über Gateway (JWT nötig)                                                                                                                         |
| `scripts/api_integration_smoke.py`      | Gateway `/health`, `/ready`, optional JWT-Health                                                                                                                                      |
