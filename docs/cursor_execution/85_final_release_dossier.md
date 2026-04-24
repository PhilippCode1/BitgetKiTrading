# Finales Release-Dossier — Run 85 (automatisierte Evidenz, P85)

**Erstellt (UTC):** 2026-04-24T14:55:52Z  
**Git HEAD:** `079c7932115d`  
**Evidenzordner:** [`85_run_evidence/`](85_run_evidence/) (inkl. `dossier_meta.json`)

Dieses Dokument ist die zentrale Management-Basis (Go/No-Go) und fasst die technischen
Nachweise aus 85+ Prompt-Iteraten zusammen — inkl. Iron-Curtain-Gate (P84), Shadow
Burn-in (P25/Readiness), UI-Evidenz (Kundenportal + Health) und AI-Reasoning-Metriken (P70).

---

## Gesamtbewertung

| Säule | Status (Run 85) | Beweis |
|-------|-----------------|--------|
| **1) Iron-Curtain-Gate (P84)** | **FAIL** | [iron_curtain.log](85_run_evidence/iron_curtain.log) (oder vgl. Konsolenauszug unten) |
| **2) Shadow-Burn-in / Readiness (P25)** | **SKIP (kein DSN/Artefakt)** | [shadow_burn_in.md](85_run_evidence/shadow_burn_in.md) (falls generiert) |
| **3) UI — Health-Grid + Kundenportal** | **SKIP (keine PNG; Playwright-Run fehlt)** | Playwright-Run, PNG in `85_run_evidence/` |
| **4) AI Reasoning Accuracy (P70)** | **SKIP (kein DSN/Artefakt)** | [reasoning_accuracy.json](85_run_evidence/reasoning_accuracy.json) & Report-Skript |

**Technischer Sammel-Status (dieser Lauf):** **UNVOLLSTÄNDIG oder NO-GO** — Säulen prüfen (oben) und Evidence nachziehen

---

## 1) Iron Curtain (P84) — vollsequenzielles Quality Gate

Status: **FAIL** — ein Fehler in einem Rand-Service (z. B. onchain-sniffer) stoppt den gesamten Durchlauf (Exit 1).

**Referenzlog / Auszug (Ende des Laufs):**

```text
Kein iron_curtain.log in 85_run_evidence/ und kein --run-iron. Befehl: pnpm release:gate:full (liefert vollstaendigen Iron-Curtain-Lauf); Log nach iron_curtain.log kopieren.
```

- Voll-Lauf: `pnpm release:gate:full` (setzt `ENVIRONMENT=production` + Iron Curtain + E2E).
- Nur Hash der Evidenz oder CI: Log nach `85_run_evidence/iron_curtain.log` speichern.

---

## 2) Shadow-Burn-in / Zertifikat (P25)

Status: **SKIP (kein DSN/Artefakt)**

- Erzeugen: `python scripts/verify_shadow_burn_in.py --hours 72 --readiness-out docs/cursor_execution/85_run_evidence/shadow_burn_in.md`
- Voraussetzung: migrierte **Postgres** mit Laufzeitdaten im Analysefenster; sonst *SKIP*.


*(Kein `shadow_burn_in.md` — siehe Befehl in Abschnitt 2.)*


---

## 3) UI-Evidenz — Operator Health + Customer Portal (100 % grüner Stack-Check visuell)

Status: **SKIP (keine PNG; Playwright-Run fehlt)**

- Headless/Playwright: `pnpm exec playwright test e2e/tests/run85_dossier_evidence.spec.ts` (E2E_BASE_URL, Gateway/Dashboard laufen).
- Erwartete PNG-Dateien:

  - *(noch nicht erzeugt)*

Vollbild-Health-Seite: **Operator `/console/health`**. Kunden**portal**: **`/portal`**, Performance: **`/portal/performance`**.

---

## 4) Reasoning Accuracy (P70)

Status: **SKIP (kein DSN/Artefakt)**

- JSON: [reasoning_accuracy.json](85_run_evidence/reasoning_accuracy.json)
- CLI: `python scripts/ai_reasoning_accuracy_report.py --limit 30 --json-out 85_run_evidence/reasoning_accuracy.json`

**Hinweis:** Leere Tabelle `learn.post_trade_review` ist ein **leeres Learning-Fenster**, kein technischer Mismatch der Pipeline — für „PASS“-Gate-Status siehe `reasoning_accuracy.json:status` (`ok` / `empty`).

---

## 5) Sammel-Artefakte (optional `collect_release_evidence.ps1`)

Bei Ingest: `collect_*` Kopien in `85_run_evidence/`.

*(kein --ingest in diesem Lauf)*

---

## Fazit (Management)

| Rolle | Aussage |
|--------|---------|
| **Produkt / Steuerkreis** | Freigabe nur nach **vollständiger** Evidenz aller Säulen; SKIP nur bei bewusstem Betrieb *ohne* DSN. |
| **Engineering (technisch)** | Evidenz unvollständig — **kein** 10/10-Beleg; Säulen oben schließen, Dossier erneut generieren. |
| **Rechtliches** | R1 ist **kein** autonomer Live-Handel; Gegenzeichnung laut [LaunchChecklist](../LaunchChecklist.md) und Betriebshandbuch. |

*Ende Dossier Run 85 (Generator: `python tools/build_run85_dossier.py`).*
