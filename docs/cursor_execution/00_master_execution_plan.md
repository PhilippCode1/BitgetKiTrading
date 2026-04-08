# Master Execution Plan — bitget-btc-ai

**Dokumenttyp:** Priorisierte Gap-Matrix, Arbeitsreihenfolge, **49-Prompt-Fahrplan**, Stop-Liste.  
**Gültig ab:** 2026-04-05.  
**Verknüpfung:** Definition of Done und Ist-Wahrheit → `docs/cursor_execution/01_repo_truth_and_done_definition.md`.

---

## 1. Ziel dieses Plans

Alle Arbeiten so steuern, dass das Projekt **messbar** den Zustand **10/10** erreicht (siehe §9 in `01_repo_truth_and_done_definition.md`). Kein Abschluss ohne **grüne, benannte** Prüfungen und dokumentierte Nachweise.

---

## 2. Priorisierte Gap-Matrix (P0 → P1 → P2)

### P0 — Blocker für jede „fertig“-Aussage

| ID           | Lücke                                    | Evidenz / Symptom                                              | Zielzustand (grün = …)                                                              |
| ------------ | ---------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **P0-TS**    | TypeScript bricht                        | `pnpm check-types` Exit 1 (`admin/page.tsx`, `paper/page.tsx`) | `pnpm check-types` Exit 0                                                           |
| **P0-FMT**   | Prettier bricht auf CI-Workflow          | `pnpm format:check` SyntaxError `ci.yml:~71`                   | `pnpm format:check` Exit 0 oder verbindlicher Prettier-Ignore + Dokumentation       |
| **P0-PY**    | production_selfcheck scheitert an Ruff   | E501 Zeile 221 in `tools/production_selfcheck.py`              | `python tools/production_selfcheck.py` Exit 0                                       |
| **P0-WIN**   | Windows-Smoke nicht lauffähig            | `pnpm smoke` → ParserError `_dev_compose.ps1` (UTF-8/Em-Dash)  | `pnpm smoke` Exit 0 mit `.env.local`                                                |
| **P0-STACK** | Kein nachgewiesener laufender Edge-Stack | Handoff 09: Gateway-Verbindung verweigert                      | `GET /ready` → `ready: true` + `docker compose ps` healthy                          |
| **P0-AUTH**  | BFF/Gateway-Auth-Drift                   | Häufige 503 durch JWT/ENV                                      | `GET /api/dashboard/edge-status` zeigt konsistente Diagnose; Mint-/ENV-Doku befolgt |

### P1 — Kernprodukt und Betrieb, nach P0

| ID           | Lücke                                 | Evidenz / Symptom                                 | Zielzustand (grün = …)                                                         |
| ------------ | ------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------ |
| **P1-SMOKE** | API-Integration nicht grün ohne Stack | `api_integration_smoke.py` scheitert an Gateway   | Script Exit 0 gegen laufendes Gateway                                          |
| **P1-SYSH**  | Aggregierte Gesundheit unbelegt       | Kein Log mit JWT auf `/v1/system/health`          | HTTP 200 + erwartete Struktur dokumentiert                                     |
| **P1-E2E**   | Playwright nicht gelaufen             | Release-Gate Spec existiert, Lauf fehlt           | `pnpm e2e` Exit 0                                                              |
| **P1-REL**   | Gesamt-Release-Gate nicht grün        | `release_gate.py` nicht mit E2E durchlaufen       | `python scripts/release_gate.py --with-e2e` Exit 0                             |
| **P1-KI**    | KI-Flow nur teilweise belegt          | Unit-Tests ≠ Live-Orchestrator                    | Operator-Explain + Strategy-Signal-Explain End-to-End grün                     |
| **P1-DATA**  | Pipeline/Frische nur dokumentiert     | Kein `/v1/live/state`-Kontrakt grün unter Windows | Bash-Skript unter WSL/CI **oder** PowerShell-Äquivalent mit gleicher Assertion |
| **P1-GIT**   | Turbo/dubious ownership Warnung       | `fatal: detected dubious ownership`               | `safe.directory` gesetzt oder Repo-Berechtigung bereinigt (dokumentiert)       |

### P2 — Qualität, UX, Observability, organisatorisch

| ID                   | Lücke                                 | Evidenz / Symptom                     | Zielzustand (grün = …)                                                                                      |
| -------------------- | ------------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **P2-PRETTIER-WARN** | Massenhafte `[warn]` bei format:check | Viele Markdown/JSON nicht formatiert  | Entweder `pnpm format` einmalig + Commit **oder** `.prettierignore` strategisch erweitern (reviewpflichtig) |
| **P2-OPENAPI**       | Vertrag vs. Code                      | Handoff 04: Parität nicht verifiziert | Optional: Diff-Job oder manuelle Stichprobe dokumentiert                                                    |
| **P2-GRAFANA**       | Dashboards Platzhalter                | REPO_TRUTH_MATRIX                     | Sinnvolle Panels oder explizite „Phase 2“-Freigabe                                                          |
| **P2-UX**            | Signaldetail/Filtersprache            | Handoff 07                            | i18n + Layertexte (kein Blocker für technisches DoD, aber für 10/10 UX)                                     |
| **P2-SHOTS**         | Keine Screenshot-Beweise              | `.gitkeep` only                       | 10+ Screenshots + README (siehe DoD §9.9)                                                                   |
| **P2-COMMERCE**      | Zahlungsfluss                         | Migrationen vorhanden, E2E offen      | Staging-Nachweis oder expliziter Scope-Ausschluss in Produktvertrag                                         |

---

## 3. Reihenfolge der nächsten Arbeiten (übergeordnet)

1. **P0-TS** — Typecheck grün (Dashboard-Typen an API-Anbindung anpassen).
2. **P0-PY** — Ruff E501 in `production_selfcheck.py` beheben.
3. **P0-FMT** — `ci.yml` für YAML/Prettier-Kompatibilität oder Prettier-Ausschluss **mit** Dokumentation.
4. **P0-WIN** — `_dev_compose.ps1` auf **ASCII-sichere** Strings oder UTF-8 mit BOM / Save-Encoding-Regel für alle `scripts/*.ps1`.
5. **P0-STACK** — `.env.local` nach `docs/LOCAL_START_MINIMUM.md`; Stack hochfahren; `/ready` dokumentieren.
6. **P1-SMOKE** + **P1-SYSH** — Integrationssmoke und System-Health mit JWT.
7. **P1-E2E** + **P1-REL** — Playwright + vollständiges Release-Gate.
8. **P1-KI** — KI-Strecken im laufenden Stack verifizieren.
9. **P2-PRETTIER-WARN** / **P2-SHOTS** / **P2-UX** — bis 10/10 UX/Observability laut Produktpriorität.

---

## 4. Stop-Liste — falsche Versprechen (ab sofort verboten)

Formulierungen und Behauptungen dieser Art dürfen **nicht** mehr getätigt werden, solange die zugehörige Prüfung nicht **grün und dokumentiert** ist:

1. **„Die Tests sind grün.“** — Verboten ohne Nennung **welcher** Befehle (z. B. nur `pytest tests/unit/...` ist kein Gesamtnachweis).
2. **„CI ist grün.“** — Verboten ohne Link/Run-ID oder lokale 1:1-Job-Nachstellung.
3. **„Der Stack läuft.“** — Verboten ohne `/ready`-JSON und Service-Status.
4. **„Typecheck/Lint ist sauber.“** — Verboten solange `pnpm check-types` / `pnpm lint` rot sind.
5. **„Format ist ok.“** — Verboten solange `pnpm format:check` fehlschlägt.
6. **„Produktionsreif / Go-Live-fähig.“** — Verboten ohne Erfüllung von `01_repo_truth_and_done_definition.md` §9.
7. **„KI handelt / autonomes Trading.“** — **Immer verboten** — widerspricht ADR und `execution_authority: none` auf den dokumentierten LLM-Strecken.
8. **„OpenAPI ist aktuell.“** — Verboten ohne Diff oder automatisierte Prüfung.
9. **„Shadow/Live ist verifiziert.“** — Verboten ohne Modus-spezifische ENV + Health + Smoke für dieses Profil.
10. **„Windows wird unterstützt.“** — Verboten solange `pnpm smoke` auf Windows mit ParserError endet.
11. **„E2E ist abgedeckt.“** — Verboten ohne `pnpm e2e` Exit 0.
12. **„UX ist 10/10.“** — Verboten ohne Screenshot- und Copy-Nachweis (Handoff 07).
13. **„Keine technische Schuld.“** — Verboten — stattdessen `[TECHNICAL_DEBT]` markieren und in Gap-Matrix führen.
14. **„Alles funktioniert.“** — Verboten ohne enumerierte Checkliste §9.

---

## 5. Verbindliche 49-Prompt-Reihenfolge (nächste Arbeitseinheiten)

Jeder Block ist **ein** sinnvoller Cursor-/Partner-Prompt; Reihenfolge einhalten, bis P0 leer ist.

| #   | Auftrag (Prompt-Kern)                                                                                                              | Ziel-„grün“                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| 1   | Analysiere `SystemHealthResponse` und Gateway-Payload; fixiere `admin/page.tsx` ohne `status`-Annahme                              | TS-Fehler 1 weg                           |
| 2   | Align `paper/page.tsx` mit Gateway-Envelope: `account_ledger_recent` optional oder Default-Array                                   | TS-Fehler 2 weg                           |
| 3   | Führe `pnpm check-types` aus und behebe alle weiteren neu sichtbaren Fehler                                                        | `pnpm check-types`                        |
| 4   | Kürze/wrappe Zeile 221 in `tools/production_selfcheck.py` für Ruff E501                                                            | `production_selfcheck.py` Ruff-Teil       |
| 5   | Vollständiger Lauf `python tools/production_selfcheck.py` mit dokumentiertem Output                                                | Exit 0                                    |
| 6   | Setze optional `DATABASE_URL` lokal und wiederhole Selfcheck für DB-Gates                                                          | Exit 0 oder dokumentiertes SKIP-Verhalten |
| 7   | Untersuche Prettier-Fehler in `ci.yml` Zeile ~71; fix YAML-Struktur oder Anführungszeichen                                         | Prettier parst Datei                      |
| 8   | Entscheide: Prettier-Ignore für `.github/**/*.yml` **oder** vollständige Format-Korrektur — dokumentiere in PR-Beschreibung        | `format:check` für Workflow               |
| 9   | Führe `pnpm format` auf restlichem Repo aus **oder** definiere `.prettierignore`-Scope — Team-Review                               | Reduzierte `[warn]`                       |
| 10  | Ersetze in `_dev_compose.ps1` alle problematischen Unicode-Zeichen durch ASCII (`-`, `...`) in **allen** betroffenen Strings       | ParserError weg                           |
| 11  | Repo-Regel: neue PS1 nur UTF-8 mit BOM oder nur ASCII — kurzer Kommentar im `scripts/README` oder bestehende Doku                  | Konvention                                |
| 12  | Führe `pnpm smoke` mit vorhandener `.env.local` aus; fixiere Folgefehler in `rc_health.ps1`                                        | Exit 0                                    |
| 13  | Validiere `.env.local` mit `pnpm config:validate`                                                                                  | Exit 0                                    |
| 14  | Starte Stack (`pnpm dev:up`); warte auf healthy; sammle `docker compose ps` Auszug                                                 | Nachweisdatei                             |
| 15  | `curl`/PowerShell: `GET /ready` am Gateway — speichere JSON Response                                                               | `ready: true`                             |
| 16  | Mint JWT falls nötig (`scripts/mint_dashboard_gateway_jwt.py`); dokumentiere Schritte                                              | JWT gültig                                |
| 17  | `GET /api/dashboard/edge-status` — prüfe `gatewayHealth`                                                                           | Diagnose grün                             |
| 18  | `GET /v1/system/health` mit Operator-JWT — speichere anonymisierte Payload-Struktur                                                | HTTP 200                                  |
| 19  | `python scripts/api_integration_smoke.py` — alle Schritte grün                                                                     | Exit 0                                    |
| 20  | Fixiere etwaige Smoke-FALSE-Positives (URLs, Ports Docker-vs-Host)                                                                 | Exit 0 stabil                             |
| 21  | Installiere Playwright Browser `pnpm e2e:install`                                                                                  | Chromium bereit                           |
| 22  | `pnpm e2e` gegen laufendes Dashboard — erste Fehler analysieren                                                                    | Exit 0                                    |
| 23  | Flaky Tests stabilisieren (Waits, ENV `E2E_BASE_URL`)                                                                              | Exit 0 wiederholbar                       |
| 24  | `python scripts/release_gate.py` ohne E2E — alle nicht-skip Teile grün                                                             | Exit 0                                    |
| 25  | `python scripts/release_gate.py --with-e2e` — vollständig                                                                          | Exit 0                                    |
| 26  | Verifiziere `verify_ai_operator_explain.py` wie Release-Gate                                                                       | Exit 0                                    |
| 27  | Strategie-Signal-Explain: E2E oder manueller Nachweis mit Log                                                                      | DoD §9.8                                  |
| 28  | Assist-Segmente: Stichprobe Health/Account                                                                                         | HTTP 200                                  |
| 29  | Terminal-Flow: Release-Gate-Test „Chart & Toolbar“ grün                                                                            | Spec grün                                 |
| 30  | Live-Broker-Seite: keine Alert-Banner bei gutem Stack                                                                              | Spec grün                                 |
| 31  | Paper-Seite: Metriken + Equity sichtbar bei Daten                                                                                  | manuell/E2E                               |
| 32  | Shadow-Live-Vergleichsseite: Smoke mit Seed-Daten                                                                                  | manuell                                   |
| 33  | Signale: Liste + Facetten ohne degrade                                                                                             | API + UI                                  |
| 34  | Signal-Detail: DB-Explain + optional LLM-Panel                                                                                     | manuell                                   |
| 35  | `pnpm build` nach allen TS-Fixes                                                                                                   | Exit 0                                    |
| 36  | `pnpm lint` — alle Warnungen entweder fix oder dokumentierte Ausnahme                                                              | Exit 0                                    |
| 37  | Rufe CI-Job `python` lokal nach (pip install wie Workflow) oder pushe und warte Actions                                            | GH Actions grün                           |
| 38  | Git `safe.directory` auf Entwickler-Windows dokumentieren (README-Kurzabschnitt)                                                   | Warnung weg                               |
| 39  | Erstelle `docs/Cursor/assets/screenshots/README.md` mit Shot-Liste                                                                 | Struktur                                  |
| 40  | Screenshots: Welcome, Konsole-Übersicht, Health+Explain, Signale, Signaldetail, Terminal, Paper, Live-Broker, Shadow-Live, Account | 10 Dateien                                |
| 41  | Mobile Screenshots (2–3 kritische Seiten)                                                                                          | DoD §9.9                                  |
| 42  | Aktualisiere `docs/chatgpt_handoff/09_*.md` mit neuem Verifikationsdatum oder verweise auf `cursor_execution`                      | Konsistenz                                |
| 43  | Abgleich `docs/REPO_TRUTH_MATRIX.md` mit Migrationen-Zahl 85                                                                       | Doku-Fix                                  |
| 44  | Optional: OpenAPI-Diff-Job-Skizze (kein Pflicht-DoD)                                                                               | Backlog                                   |
| 45  | Optional: Grafana-Kernpanels befüllen                                                                                              | P2                                        |
| 46  | UX: Signaldetail „Kurzfassung“-Block (Handoff 07)                                                                                  | P2                                        |
| 47  | Filter-Labels i18n (market_family → Lesbarkeit)                                                                                    | P2                                        |
| 48  | Abschlussreview: alle §9 in `01_*.md` abhaken mit Links/Logs                                                                       | 10/10                                     |
| 49  | Freeze-Tag: Commit SHA + „Done Definition erfüllt“ in `RELEASE`-Notiz oder `PRODUCT_STATUS.md` kurzer Statusblock                  | Release-Record                            |

---

## 6. Kurze Testanleitung (nach Umsetzungsphasen)

```text
pnpm check-types
pnpm lint
pnpm build
pnpm format:check
python tools/production_selfcheck.py
pnpm smoke
docker compose ps
# PowerShell:
Invoke-RestMethod http://127.0.0.1:8000/ready
python scripts/api_integration_smoke.py
pnpm e2e
python scripts/release_gate.py --with-e2e
```

Unter Linux/WSL zusätzlich: `bash scripts/healthcheck.sh` (mit `HEALTHCHECK_EDGE_ONLY=true` für Shadow-Stil).

---

## 7. Bekannte offene Punkte

- **Organisatorisches Go-Live** (Verträge, Compliance, Bitget-Produktionsfreigaben) — **außerhalb** Repo-DoD, siehe `docs/LAUNCH_DOSSIER.md`.
- **Echter Live-Handel** — kein verpflichtendes DoD-Kriterium; Safety und Operator-Gates bleiben führend.
- **[RISK]** Exchange-API-Änderungen Bitget — Monitoring über `docs/PROVIDER_ERROR_SURFACES.md`.
- **[TECHNICAL_DEBT]** Viele Markdown-Warnungen bei Prettier — bewusst nach P0/P1 schedulen.

---

## 8. Pfad-Index

| Thema                       | Pfad                                                         |
| --------------------------- | ------------------------------------------------------------ |
| Definition of Done (detail) | `docs/cursor_execution/01_repo_truth_and_done_definition.md` |
| Handoff                     | `docs/chatgpt_handoff/01`–`09`                               |
| Windows Compose-Helfer      | `scripts/_dev_compose.ps1`, `scripts/rc_health.ps1`          |
| Release-Gate                | `scripts/release_gate.py`                                    |

---

_Ende der Datei._
