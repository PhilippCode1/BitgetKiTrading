# CI- und Release-Qualitätsvertrag

Stand: 2026-04-05

## Zweck

Ein **harter Vertrag** für das Team: Welche Signale müssen **grün** sein, bevor von „fertig“, „mergebereit“, „release ready“ oder „produktionstauglich“ die Rede ist. Diese Datei ist die **Referenz**; sie ergänzt `.github/workflows/ci.yml`, `scripts/release_gate.py` und `package.json`.

---

## Begriffe

| Begriff                 | Bedeutung hier                                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Merge (main)**        | Pull Request wird auf `main`/`master` gemerged; CI muss laut Branch-Protection grün sein.                           |
| **Release ready**       | Produktionsnahe Freigabe: statische Gates + **laufender Stack** + HTTP-/E2E-Smokes wie unten.                       |
| **Produktionstauglich** | Wie Release ready **und** Betriebs-Checklisten (Secrets, Monitoring, Runbooks) — nicht vollständig automatisierbar. |

---

## Pflicht vor Merge (GitHub Actions)

Voraussetzung: Workflow **`ci`** auf dem PR-Commit **vollständig grün** (alle erforderlichen Jobs). Konkret (Stand Workflow):

| Job                       | Was geprüft wird (Kurz)                                                                                                                                                                                                                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **`python`**              | ENV-Profil-Beispiel, Shell-`bash -n`, `release_sanity_checks`, ENV-Template-Security, Ruff/Black/Mypy (Kern, inkl. `scripts/release_gate.py`), LLM-Baseline, Schema + Contracts, Migrationen + `modul_mate_selfcheck` **mit** DB, Pytest (unit + integration marker), Coverage-Gates, Wheel, pip-audit |
| **`dashboard`**           | `pnpm install`, **`pnpm check-types`** (Turbo: Dashboard **und** shared-ts), **`pnpm format:check`**, Jest `test:ci`, `next build`, `pnpm audit --audit-level=high`                                                                                                                                    |
| **`compose_healthcheck`** | Nur wenn **nicht** `schedule`: Compose config, `up`, `healthcheck.sh`, `rc_health_runner`, KI-Orchestrator-Smoke, **Playwright** `e2e/playwright.config.ts`                                                                                                                                            |

**Zeitplan:** Der `compose_healthcheck`-Job läuft **nicht** beim wöchentlichen `schedule`-Lauf (Kosten); Merge auf `main`/`master` soll ihn weiterhin als Pflicht behandeln (PR/Push).

### Branch-Protection (außerhalb des Repos, GitHub)

Im Repository unter **Settings → Branches → Branch protection rule** (für `main` und ggf. `master`):

1. **Require a pull request before merging** (empfohlen).
2. **Require status checks to pass before merging** — mindestens diese Checks aus dem Workflow `ci` anhaken:
   - `python`
   - `dashboard`
   - `compose_healthcheck` (sofern der Job für PRs existiert; bei reinen Docs-Änderungen ggf. Workflow-Regel prüfen)
3. **Require branches to be up to date before merging** (empfohlen).

Ohne diese Einstellungen ist der „Pflicht vor Merge“-Vertrag technisch nicht durchsetzbar.

---

## Pflicht vor Release (lokal oder Release-Pipeline)

**Minimum:** Alle **Merge-Pflichten** erfüllt (grüne CI auf dem Release-Commit).

**Zusätzlich vor produktionsnaher Freigabe:**

| Schritt                        | Befehl / Aktion                                                           | Voraussetzung                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Statische Nähe zu CI (schnell) | `pnpm quality:static`                                                     | Python + pnpm installiert; entspricht `check-types` + `format:check` + `production_selfcheck` |
| Release-Gate (Runtime)         | `pnpm release:gate` bzw. `python scripts/release_gate.py`                 | Gateway/Dashboard wie in `.env.local` / Defaults erreichbar; sonst schlagen HTTP-Smokes fehl  |
| Mit E2E                        | `pnpm release:gate:full` oder `python scripts/release_gate.py --with-e2e` | Dashboard unter `E2E_BASE_URL` (Standard `http://127.0.0.1:3000`)                             |
| Optional Stack überspringen    | `SKIP_STACK_SMOKES=1`, `SKIP_DASHBOARD_PROBE=1`                           | Nur für **eingeschränkte** Diagnose — **nicht** als „release ready“ verkaufen                 |

**Hinweis:** `release_gate` startet immer mit `tools/production_selfcheck.py`. Es ersetzt **nicht** die volle CI-Python-Suite (z. B. gesamte `pytest tests` mit Coverage); dafür ist **CI** maßgeblich.

---

## Lokale Kommandos und CI-Parität

| Kommando                               | Rolle                                                                                  | CI-Äquivalent / Abgleich                                                                                                |
| -------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `pnpm check-types`                     | Turbo `check-types` (Dashboard + shared-ts)                                            | Job **dashboard**: explizit `pnpm check-types`                                                                          |
| `pnpm format:check`                    | Prettier Repo-Root                                                                     | Job **dashboard**: `pnpm format:check`                                                                                  |
| `pnpm smoke` / `pnpm rc:health`        | PowerShell `scripts/rc_health.ps1`                                                     | CI **compose_healthcheck**: `bash scripts/healthcheck.sh` + `rc_health_runner.py` (gleiche **Intention**, andere Shell) |
| `pnpm api:integration-smoke`           | `scripts/api_integration_smoke.py`                                                     | In **release_gate** enthalten; **nicht** als eigener Step im Python-CI-Job, aber Compose-Job prüft Stack-Gesundheit     |
| `pnpm e2e`                             | Playwright lokal                                                                       | CI **compose_healthcheck**: `pnpm exec playwright test -c e2e/playwright.config.ts`                                     |
| `python tools/production_selfcheck.py` | Kern-Python: Ruff-Pfade, Black-Subset, Mypy-Kern, Kern-Pytests, contracts, schema, ENV | CI **python**: Ruff/Black breiter; volle Pytest-Suite + Migrationen + DB-Gates zusätzlich                               |
| `pnpm quality:static`                  | Ein Befehl: Types + Format + Python-Selfcheck                                          | Teilmenge von CI; **schneller** Merge-Vorabcheck                                                                        |

**Korrektur zu älteren Notizen (z. B. Handoff 09):** Typecheck für **shared-ts** erfolgt über **`pnpm check-types`** im **Repo-Root**, nicht über ein eigenes Script nur in `shared/ts`.

---

## Was „dieselbe Qualität“ heißt — und wo bewusst differenziert wird

- **Einheitlich:** TypeScript-Typen (Turbo), Prettier am Repo-Root, Dashboard-Tests und -Build, Supply-Chain-Audit (pnpm), zentrale Python-Verträge (`check_contracts`, `check_schema`), Modul-Mate-Migration + DB-Gates in CI.
- **CI strenger als `production_selfcheck`:** Voller `pytest`-Scope, Integrationstests, Coverage-Gates, pip-audit, breitere Ruff-/Black-Pfade.
- **`release_gate`:** Fokus **laufender Stack** + HTTP/Probes/E2E; statischer Teil beginnt mit `production_selfcheck`, nicht mit kompletter CI-Python-Matrix.
- **Windows vs. Linux CI:** Lokaler `pnpm smoke` nutzt PowerShell; CI nutzt Bash — beide sollen auf **denselben fachlichen** Kriterien (Edge healthy, rc_health, …) basieren; Abweichungen nur in der Shell-Schicht.

---

## Checkliste Kurz

**Vor jedem PR (empfohlen):**

```bash
pnpm quality:static
```

**Vor Merge:**

- GitHub Actions **`ci`** grün + Branch-Protection aktiv.

**Vor Release:**

- CI grün auf Release-Commit
- `pnpm release:gate` (und bei Bedarf `--with-e2e`)
- Manuelle betriebliche Punkte (Secrets, SLOs, Runbooks) laut `docs/stack_readiness.md` / Operations-Docs

---

## Offene Punkte

- **Branch-Protection** muss im GitHub-UI gesetzt werden — im Git selbst nicht versionierbar.
- **compose_healthcheck** auf `schedule` absichtlich aus — wöchentlicher Lauf ohne Compose; Merge-Anforderung bleibt PR/Push-basiert.
