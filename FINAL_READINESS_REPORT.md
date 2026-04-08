# Finaler Readiness-Report — technische Endbewertung

**Stand:** 2026-04-02 (Repo-Zustand nach KI-Strecke, Umgebungsparität, Observability, CI-Härtung).  
**Methode:** Abgleich von Code, CI-Workflow, Skripten und kanonischer Doku — **kein** externes Produktions-Audit, **kein** Pen-Test, **keine** verifizierte Live-Exchange-Last in diesem Schritt.

**Leitlinie:** Jede positive Aussage verweist auf einen **Nachweis** im Repo. Unbekanntes oder rein Organisatorisches ist als **Risiko** oder **Lücke** benannt.

---

## Gesamteinschätzung (realistische 10er-Skala)

| Bewertung                                      | Wert       | Begründung                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ---------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Gesamt: „Nähe zu starker Betriebsfreigabe“** | **7 / 10** | Die **Software- und Qualitätsseite** (CI-Gates, nachweisbare KI-Strecke, Doku, Observability-Dokumentation) ist **über Durchschnitt** für ein komplexes Monorepo. Eine **ehrliche 10/10** würde **belegte** Produktionsläufe inkl. Backup/Restore-Übung, abgeschlossenes Shadow-Burn-in, wirkungsvolles Alert-Routing und **keine** offenen P0-Themen aus der Gap-Matrix erfordern — das kann ein Repo **allein** nicht erfüllen. |
| **Keine 10/10**                                | —          | Begründung: `docs/LAUNCH_DOSSIER.md` §5 (externe Blocker), `docs/REPO_FREEZE_GAP_MATRIX.md` (restliche P1/P2), Recovery nur **dokumentiert** nicht **repo-seitig automatisch verifiziert**; Playwright läuft im Compose-CI-Job, ersetzt aber kein Staging-Burn-in und keine org. Freigaben.                                                                                                                                       |

---

## Teilbereiche

### 1. Benutzerführung & Operator-UX (Dashboard)

| Feld                 | Inhalt                                                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10**                                                                                                                                                                                              |
| **Nachweis**         | Operator-Konsole mit Health inkl. **Operator Explain**-Panel (`OperatorExplainPanel.tsx`); i18n `de.json` / `en.json`; BFF-Fehlerpfade (`operator-explain-errors.ts`, `qa-report.md`).                  |
| **Offene Risiken**   | Nicht alle Produktflächen wurden einzeln auf Vollständigkeit geprüft; Browser-E2E deckt **Kernpfade** ab, keine Garantie für jede Unterseite (`e2e/tests/release-gate.spec.ts`, `tests/e2e/README.md`). |
| **Nächster Schritt** | Onboarding- und Landing-Texte bei jedem neuen sichtbaren Feature abstimmen (`PRODUCT_STATUS.md` §3); Staging-Smoke mit Protokoll.                                                                       |

### 2. Sprache & Konsistenz (i18n)

| Feld                 | Inhalt                                                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10**                                                                                                                                                                |
| **Nachweis**         | Zentrale Message-Dateien `apps/dashboard/src/messages/de.json`, `en.json`; Fehlertexte für KI-Flow explizit.                                                              |
| **Offene Risiken**   | Einzelne ältere `docs/` oder UI-Strings können von der „kanonischen“ Statussprache abweichen (`docs/operator_status_language.md` als Referenz, keine Vollaudit-Garantie). |
| **Nächster Schritt** | Gezielter Review kritischer Konsole-Seiten vs. `operator_status_language.md`.                                                                                             |

### 3. Zentrale Seiten & „vollständiger“ Produktumfang

| Feld                 | Inhalt                                                                                                                                              |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **6 / 10**                                                                                                                                          |
| **Nachweis**         | Viele Routen unter `apps/dashboard/src/app/(operator)/console/`; `PRODUCT_STATUS.md` listet **eine** end-to-end KI-Funktion als bewusst fokussiert. |
| **Offene Risiken**   | „Vollständig“ ist nicht formal definiert; weitere LLM-Endpunkte sind **nicht** alle über Dashboard+BFF exponiert.                                   |
| **Nächster Schritt** | Produkt-Backlog: explizite „Scope-Liste Sichtbarkeit“ vs. `docs/LAUNCH_PACKAGE.md`.                                                                 |

### 4. APIs & Gateway

| Feld                 | Inhalt                                                                                                                                                                                                                               |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Reifegrad**        | **8 / 10**                                                                                                                                                                                                                           |
| **Nachweis**         | Zentrales Gateway mit Auth, Rate-Limits, `GET /v1/system/health`, `POST /v1/llm/operator/explain`; Unit-Tests z. B. `tests/unit/api_gateway/test_routes_llm_operator.py`; Smoke `scripts/rc_health_edge.py` prüft mehrere Lesepfade. |
| **Offene Risiken**   | JWT-/Auth-Modus abhängig von ENV; Fehlkonfiguration führt zu 401/403 (erwartbar, aber operativ relevant).                                                                                                                            |
| **Nächster Schritt** | Branch-Protection mit erzwungenen CI-Checks (`docs/ci_release_gates.md`).                                                                                                                                                            |

### 5. KI-Strecke (nachweisbar)

| Feld                 | Inhalt                                                                                                                                                                                                                                    |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **8 / 10** (für **einen** Pfad)                                                                                                                                                                                                           |
| **Nachweis**         | Architektur `AI_FLOW.md`; Tests `tests/llm_orchestrator/test_structured_fake_provider.py`; CI-Compose: `verify_ai_operator_explain.py --mode orchestrator`; Trace-IDs BFF→Gateway→Orchestrator (`OBSERVABILITY_AND_SLOS.md`, Middleware). |
| **Offene Risiken**   | OpenAI abhängig von Key/Quota; Fake-Provider **nicht** in Shadow/Prod (`config/settings.py` Validierung).                                                                                                                                 |
| **Nächster Schritt** | Staging: ein Lauf mit `LLM_USE_FAKE_PROVIDER=false` und echtem Key **dokumentiert** festhalten.                                                                                                                                           |

### 6. Reproduzierbarer Start

| Feld                 | Inhalt                                                                                                                                                                       |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10**                                                                                                                                                                   |
| **Nachweis**         | `README.md`, `docs/LOCAL_START_MINIMUM.md`, Compose, `scripts/healthcheck.sh`, `pnpm stack:*`; CI beweist **einen** erfolgreichen Compose-Pfad mit generierter `.env.local`. |
| **Offene Risiken**   | Erfolg hängt von Host (Docker, Ports, Windows vs. Linux), echter `.env.local` vs. Template ab.                                                                               |
| **Nächster Schritt** | Team-„Gold-Image“-Notiz: eine referenzierte Compose-Override-Datei + dokumentierte Mindest-ENV.                                                                              |

### 7. Umgebungen (local / staging / prod)

| Feld                 | Inhalt                                                                                                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10**                                                                                                                                                                                                                |
| **Nachweis**         | `config/required_secrets_matrix.json` (v2, `staging`-Spalte), `tools/validate_env_profile.py`, `STAGING_PARITY.md`, `docs/SECRETS_MATRIX.md`; Dashboard: kein stiller Prod-Fallback für URLs (`server-env.ts`, `env.ts`). |
| **Offene Risiken**   | **Konkrete** Staging-Instanz wird im Repo nicht betrieben; Abweichungen nur durch **euch** verifizierbar.                                                                                                                 |
| **Nächster Schritt** | Einmal `staging_smoke.py` gegen echte Staging-URLs in Runbook eintragen.                                                                                                                                                  |

### 8. Beobachtbarkeit

| Feld                 | Inhalt                                                                                                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10**                                                                                                                                                                             |
| **Nachweis**         | Prometheus-Middleware `shared_py.observability.metrics`; Gateway Request-ID; `docs/observability.md`, `docs/observability_slos.md`, `OBSERVABILITY_AND_SLOS.md`; Grafana-JSON im Repo. |
| **Offene Risiken**   | **Alertmanager→On-Call** ist Infrastruktur; ohne eure Verdrahtung bleiben Regeln „nur Code“.                                                                                           |
| **Nächster Schritt** | Mindestens ein **Pager/Slack**-Kanal pro kritischem Alert aus `infra/observability/prometheus-alerts.yml` zuweisen und testen.                                                         |

### 9. Qualitätsgates & CI

| Feld                 | Inhalt                                                                                                                                                                                                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **8 / 10**                                                                                                                                                                                                                                                                             |
| **Nachweis**         | `.github/workflows/ci.yml`: Python (Lint, Tests, Coverage-Gates, pip-audit), Dashboard (lint, test, build, audit), Compose+Health+`rc_health_runner`+**KI-Smoke**+**Playwright** (`e2e/playwright.config.ts`); `docs/ci_release_gates.md` inkl. wöchentlichem Light-Lauf ohne Compose. |
| **Offene Risiken**   | Branch-Protection muss im **Git-Host** gesetzt werden (Doku beschreibt, Erzwingung nicht im Repo).                                                                                                                                                                                     |
| **Nächster Schritt** | Required Checks für `main` aktivieren.                                                                                                                                                                                                                                                 |

### 10. Releasefähigkeit & Rollback

| Feld                 | Inhalt                                                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10** (Doku + Gates); **5 / 10** (ohne org. Freigaben)                                                                             |
| **Nachweis**         | `docs/LAUNCH_DOSSIER.md`, `docs/LaunchChecklist.md`, `docs/ci_release_gates.md` (Freigabe/Rollback-Abschnitte), `release-readiness.md`. |
| **Offene Risiken**   | Rollback ist **prozedural** beschrieben; tatsächliche Image-Registry/Helm-Rollback liegt außerhalb des Repos.                           |
| **Nächster Schritt** | Ein **Dry-Run Rollback** in Staging dokumentieren (Zeit, Verantwortliche).                                                              |

### 11. Sicherheit

| Feld                 | Inhalt                                                                                                                                                                                            |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **7 / 10**                                                                                                                                                                                        |
| **Nachweis**         | Gateway-Auth, interne Service-Keys, `check_production_env_template_security.py`, `pip_audit_supply_chain_gate.py`, `docs/api_gateway_security.md`; `DASHBOARD_GATEWAY_AUTHORIZATION` server-only. |
| **Offene Risiken**   | Kein externes Pen-Test in diesem Report; Secret-Rotation und Vault-Betrieb organisatorisch (`LAUNCH_DOSSIER` §6).                                                                                 |
| **Nächster Schritt** | Externes Security-Review oder zumindest OWASP-Top-10-Checkliste für öffentliche Endpunkte.                                                                                                        |

### 12. Datenverlust, Recovery, Live-Schalter

| Feld                 | Inhalt                                                                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Reifegrad**        | **5–6 / 10**                                                                                                                                           |
| **Nachweis**         | Runbooks: `docs/prod_runbook.md`, `docs/emergency_runbook.md`, `docs/LAUNCH_DOSSIER.md` §3; Forensik-/Audit-Hinweise in Doku.                          |
| **Offene Risiken**   | **Backup/Restore-Übung** und RTO/RPO sind **nicht** durch dieses Repo belegt; Kill-Switch/Safety-Verhalten hängt von korrektem Live-Broker-Betrieb ab. |
| **Nächster Schritt** | Ein **messbarer** Postgres-Restore-Test + dokumentiertes Ergebnis; Tischübung Kill-Switch.                                                             |

### 13. Externe Provider (Bitget, OpenAI, …)

| Feld                 | Inhalt                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| **Reifegrad**        | **6 / 10**                                                                                               |
| **Nachweis**         | Integration über konfigurierte Clients; Demomodi dokumentiert; `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`.  |
| **Offene Risiken**   | Quota, Ausfälle, regionale Sperren — **kein** Repo-Substitut; Live-Trading erfordert Exchange-Freigaben. |
| **Nächster Schritt** | Monitoring der Bitget-„public health“ und LLM-Fehlerquote in Staging (`OBSERVABILITY_AND_SLOS.md`).      |

---

## P0 / P1 — was im Repo noch auffällt

| Priorität | Thema                                 | Status / Hinweis                                                                                                 |
| --------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **P1**    | Fixture-/Symbol-Drift (BTCUSDT-Reste) | `REPO_FREEZE_GAP_MATRIX.md` — teilweise behoben, Rest **major** für saubere Operatoren-Erwartung.                |
| **P1**    | Replay-/Determinismus LLM-Backoff     | `PRODUCT_STATUS.md`, `LaunchChecklist` — LLM nicht bit-für-bit replaybar; für Trading-Kern akzeptiert mit Scope. |
| **P1**    | Shared TS / OpenAPI-Parität           | Gap-Matrix P2 — technische Schuld, nicht automatisch Blocker für einen KI-Pfad.                                  |
| **—**     | Branch-Protection                     | **Operativ P0 für „main deploybar“** — muss im GitHub/GitLab gesetzt werden (nicht im Git-Inhalt).               |

---

## Restplan bis zu einer „starken“ Betriebsfreigabe (knallklar)

1. **Organisation:** Branch-Protection + ein verifizierter **Staging-Stack** laut `STAGING_PARITY.md` (kein Loopback in Gateway-Containern für `HEALTH_URL_*`).
2. **Betrieb:** Postgres-**Restore-Test** + Alertmanager→On-Call; ein dokumentiertes **Shadow-Burn-in**-Ergebnis (`docs/shadow_burn_in_ramp.md`).
3. **Produkt:** P1-Gap „Symbol/Fixture-Drift“ und gewünschte **Browser-Smokes** abarbeiten oder explizit als Risiko akzeptieren (Schriftform).

---

## Nächste 3 technisch sinnvolle Schritte (wenn Ziel noch nicht erreicht)

1. **Git-Host:** Required Status Checks für `python`, `dashboard`, `compose_healthcheck` auf `main` aktivieren (`docs/ci_release_gates.md`).
2. **Staging:** Ein erfolgreicher Lauf von `scripts/staging_smoke.py` (inkl. Gateway-JWT) mit Protokoll (Zeit, SHA, Umgebung).
3. **Recovery:** Ein dokumentierter Postgres-Restore (RTO/RPO-Notiz) + Referenz auf `docs/prod_runbook.md` aktualisieren.

---

## Querverweise (kanonisch)

| Thema                          | Datei                            |
| ------------------------------ | -------------------------------- |
| Produktstatus / ehrliche Liste | `PRODUCT_STATUS.md`              |
| Launch-Stufen G0–G5            | `docs/LAUNCH_DOSSIER.md`         |
| Checkboxen                     | `docs/LaunchChecklist.md`        |
| CI-Gates, Rollback-Kurz        | `docs/ci_release_gates.md`       |
| KI-Fluss                       | `AI_FLOW.md`                     |
| Observability / SLOs           | `OBSERVABILITY_AND_SLOS.md`      |
| Staging-Parität                | `STAGING_PARITY.md`              |
| Gap-Matrix                     | `docs/REPO_FREEZE_GAP_MATRIX.md` |
