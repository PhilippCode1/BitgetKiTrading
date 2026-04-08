# Prompt 10 — Finale Live-App: Release-Bericht und Go/No-Go

**Stand:** Abschlussarbeit nach Prompts 6–9 (Produkt-UI, Incidents, Integrations-Check, E2E-Gate).  
**Ehrlichkeit:** Ein Repo allein kann **keinen** Produktions-Go ohne laufenden Stack, gültige Secrets und manuelle Abnahme ersetzen.

---

## 1. In diesem Schritt geänderte / bereinigte Dateien

| Datei                                                    | Änderung / Ursache                                                                                                                                                                                                             |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `apps/dashboard/src/lib/health-warnings-ui.ts`           | **Toter Code entfernt:** `parseOpsExtraWarning` / `OpsExtraWarning` (nirgends mehr genutzt; Ops nutzt strukturierte Integration + `PanelDataIssue`).                                                                           |
| `apps/dashboard/src/app/(operator)/console/ops/page.tsx` | **I18n:** sichtbare Ops-Zeilen (Katalog-Snapshot, Capability-Kategorien, Fokus-Erklärung, Drift-Titel, Degradation-Überschrift, Ausführungs-`<details>`-Summary, Health-Warnung „betroffene Dienste“) auf `t(...)` umgestellt. |
| `apps/dashboard/src/messages/de.json`                    | Neue Keys unter `pages.ops.*` für die obigen Texte.                                                                                                                                                                            |
| `apps/dashboard/src/messages/en.json`                    | Entsprechende englische Strings.                                                                                                                                                                                               |

**Bereits in früheren Prompten umgesetzt (Kontext, nicht erneut geändert):** Incident-Banner, Integrationsmatrix + `/console/integrations`, `dashboard_page_probe.py`, `release_gate.py`, Playwright `e2e/tests/release-gate.spec.ts`, Terminal-Fallback ohne fingierte DB/Redis-Fehler, usw.

---

## 2. Behobene / adressierte Ursachen

- **Redundanter Diagnosepfad:** Entfernung der ungenutzten Ops-String-Parser-Funktion → weniger verwirrende Duplikate neben dem echten Health-/Integrationsmodell.
- **Uneinheitliche Oberflächensprache (Teilbereich Ops):** Kopf- und Statuszeilen am Cockpit nutzen jetzt die gleiche i18n-Kette wie der Rest der Konsole (weitere Panel-Texte auf der Ops-Seite können iterativ nachgezogen werden).

---

## 3. Verbleibende Restrisiken (bewusst nicht „wegprogrammierbar“)

| Risiko                                 | Begründung                                                                                                                                                                                                                    |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ops-Seite: weiteres Hardcoding**     | Viele Tabellenköpfe, Leerzustände und technische Sätze sind noch deutsch/englisch fix im JSX — funktional OK, aber i18n unvollständig.                                                                                        |
| **HealthGrid / weitere Panels**        | Teilstrings noch nicht über `messages/*` (z. B. „Execution Controls“).                                                                                                                                                        |
| **Echter Stack**                       | Kein automatischer Nachweis in diesem Commit, dass **dein** Gateway, DB, Redis und alle `HEALTH_URL_*` grün sind — dafür `pnpm api:integration-smoke`, `pnpm dashboard:probe`, optional `PLAYWRIGHT_E2E=1 pnpm release:gate`. |
| **Telegram / Zahlungen / Bitget Live** | Externe Konten, Webhooks, Keys; E2E deckt UI ab, nicht Vertrags-/Compliance-Freigaben.                                                                                                                                        |
| **Staging ≠ Prod**                     | Parität und Secrets-Rotation sind organisatorisch (siehe `PLAN_BETRIEBSBEREIT_10_VON_10.md`).                                                                                                                                 |

---

## 4. Endtest (empfohlene Reihenfolge)

Auf dem **Referenz-Rechner** mit gültiger `.env.local`:

1. `pnpm config:validate:operator` (oder euer Profil)
2. Stack starten (z. B. `pnpm stack:local` / `pnpm dev:up` laut README)
3. Dashboard mit `DASHBOARD_GATEWAY_AUTHORIZATION` starten
4. `pnpm api:integration-smoke`
5. `pnpm dashboard:probe` (Dashboard unter `DASHBOARD_BASE_URL` erreichbar)
6. Optional: `pnpm e2e:install` dann `PLAYWRIGHT_E2E=1 pnpm release:gate`
7. Manuell: `/console/integrations`, `/console/health`, ein Live-Lesepfad (Signale oder Terminal)

**In dieser Umgebung (CI-Agent):** Nur statische Checks möglich — kein Ersatz für Schritte 2–7 auf eurer Hardware.

---

## 5. Release-Empfehlung

### No-Go (hart), wenn eines zutrifft

- `api_integration_smoke` schlägt fehl (Gateway nicht erreichbar, `/ready` nicht ready, oder JWT-Health mit DB/Redis ≠ ok).
- `dashboard_page_probe` schlägt fehl (HTTP ≠ 200, fehlende Shell, `msg-err` im `<main>` auf Kernseiten).
- Kritische Sicherheits- oder Launch-Checklisten (`docs/LAUNCH_DOSSIER.md`, interne Policy) sind nicht erfüllt.

### Go (bedingt), wenn

- Obige automatisierten Schritte **grün** sind auf dem **Ziel-Environment** (mindestens Staging).
- Integrationsmatrix zeigt keine `error`/`misconfigured` für für euch **kritische** Zeilen (Broker, Gateway/DB/Redis, ggf. LLM).
- Ein **menschlicher** Operator hat Cockpit + einen Datenpfad (Signale/Learning) kurz gegen die Realität geprüft.

### Kurzfassung

**Kein blindes „Go Live“** aus dem Repo allein — **Go** für Code-Merge/Release-Kandidat, wenn euer Stack-Smoke + Probes + kurze manuelle Abnahme grün sind; sonst **No-Go** bis die Ursache in ENV, Netzwerk oder Diensten behoben ist.

---

## 6. Nächste sinnvolle Iterationen (nach Prompt 10)

- Restliche `ops/page.tsx`-Strings in `pages.ops.*` auslagern (inkl. Tabellen-Header, Leerzustände).
- `HealthGrid` und ähnliche Panels auf gemeinsame Übersetzungskeys.
- CI-Job, der `api_integration_smoke` gegen einen bereitgestellten Stack (Service-Container) ausführt — optional, aufwändig.

Siehe auch: `API_INTEGRATION_STATUS.md` §9 (E2E/Release-Gate), `docs/integrations_matrix.md`, `docs/PLAN_BETRIEBSBEREIT_10_VON_10.md`.
