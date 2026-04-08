# 43 — Signaldetail: menschliche Oberseite, technische Unterseite

**Ziel:** Die Seite `/console/signals/[id]` wirkt oben **editorial** (Kurzfassung, Chart, Risiko, gespeicherte Erklärung, Live-KI) und führt **Rohfelder** nur im **aufklappbaren Operatoren-Bereich**.

**Datum (Umsetzung):** 2026-04-05.

---

## 1. Seitenstruktur (Reihenfolge)

1. **Kopf:** `Header` mit `heroTitle` / `heroSubtitle` (Symbol, Zeitrahmen, gekürzte Signal-ID) — keine technischen Feldnamen im Titel.
2. **Zurück-Link** zur Signalliste.
3. **`SignalDetailLlmChartProvider`** umschließt:
   - **Kurzfassung** — `SignalDetailHumanSummary` (`ContentPanel`, Disclaimer, Glossar-Hinweis).
   - **Chart** — `SignalDetailMarketChartBlock` (bestehende i18n `chartTitle`, LLM-Overlay wie zuvor).
   - **Risiko & Strategie** — `SignalDetailRiskStrategySection` (Snapshot-Zeilen, `RiskWarningsPanel`, No-Trade-/Trade-Rationale).
   - **Gespeicherte Erklärung** — `SignalDetailStoredExplainSection` (Layer 1–3 menschlich; **kein** `reasons_json` im Fließtext — Hinweis auf Technikbereich).
   - **Hinweis Schicht 4** — `explainLayer4Aside` (muted).
   - **Live-KI + Strategie-Entwurf** — `SignalDetailLiveAiSection` → `StrategySignalExplainPanel`, `StrategyProposalDraftPanel`.
4. **Technik (aufklappbar)** — `SignalDetailTechnicalCollapsible`: Kennzahlen-Grid mit `techMetrics.*`, Instrument/Routing, Stop, Execution/Telegram, JSON-Blöcke, **vollständiges `reasons_json`** (Explain bevorzugt, sonst Signalzeile).

---

## 2. Betroffene Dateien (Überblick)

| Bereich              | Pfad                                                                                                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Seite                | `apps/dashboard/src/app/(operator)/console/signals/[id]/page.tsx`                                                                                                                      |
| Komponenten          | `SignalDetailHumanSummary.tsx`, `SignalDetailRiskStrategySection.tsx`, `SignalDetailStoredExplainSection.tsx`, `SignalDetailLiveAiSection.tsx`, `SignalDetailTechnicalCollapsible.tsx` |
| i18n                 | `apps/dashboard/src/messages/de.json`, `en.json` (`pages.signalsDetail.*`)                                                                                                             |
| Styles               | `apps/dashboard/src/app/globals.css` (`.signal-detail-*`, `.signal-detail-technical-*`)                                                                                                |
| Trade-Action-Mapping | `apps/dashboard/src/lib/signal-detail-trade-action.ts`                                                                                                                                 |
| Test                 | `apps/dashboard/src/lib/__tests__/signal-detail-trade-action.test.ts`                                                                                                                  |

---

## 3. i18n / Offenlegung

- Neue Keys u. a.: `summary*`, `sectionRisk*`, `sectionStored*`, `riskSnapshot*`, `tradeActions.*`, `tech*`, `techMetrics.*`, `heroTitle` / `heroSubtitle`, `boolYes` / `boolNo`, `explainLayer3LeadHuman`, `explainLayer3RawHint`.
- Operatoren-Bereich: **API-Namen** als `mono-small`-Labels beibehalten; erklärende Absätze über `techGroup*Lead`, `techStopAuditHint`, `techPolicyBody`.

---

## 4. Nachweise

### 4.1 Ausgeführte Befehle (2026-04-05, Windows / PowerShell)

| Kommando                                                                                              | Ergebnis                                                                                 |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `pnpm check-types` (Repo-Root)                                                                        | **Exit 0** — `@bitget-btc-ai/dashboard` und `@bitget-btc-ai/shared-ts` `tsc --noEmit` ok |
| `pnpm test -- src/lib/__tests__/signal-detail-trade-action.test.ts --runInBand` (in `apps/dashboard`) | **Exit 0** — 3 Tests bestanden                                                           |
| `pnpm test -- src/lib/__tests__/signal-explain-display.test.ts --runInBand` (in `apps/dashboard`)     | **Exit 0** — 3 Tests (`summarizeReasonsJsonForUi`, genutzt in gespeicherter Erklärung)   |

### 4.2 Signaldetail-UI-Nachweis (manuell)

1. Konsole starten, angemeldet als Operator, `/console/signals` öffnen und ein Signal wählen.
2. **Erwartung oben:** Block „Kurzfassung“ mit Fließtext (Symbol, Zeitrahmen, Richtung, Handlungsvorschlag), **kein** `canonical_instrument_id` / `stop_fragility_0_1` sichtbar.
3. Direkt darunter **Chart** (Kontext-Chart).
4. Danach **Risiko & Strategie**, **Gespeicherte Erklärung**, Hinweis Schicht 4, **Live-KI**-Ribbon und Panels.
5. **Unten:** Aufklapper „Technische Details für Operatoren“ — dort Kennzahlen-Grid, Persistenzfelder, JSON, `reasons_json`.

---

## 5. Screenshots (Platzhalter)

Lege verifizierte Screens unter **`docs/Cursor/assets/screenshots/`** ab (Namensvorschlag):

- `signal-detail-43-human-top.png` — sichtbar: Kurzfassung, Chart-Kopf.
- `signal-detail-43-technical-collapsed.png` — Technik-Bereich zugeklappt.
- `signal-detail-43-technical-open.png` — Technik-Bereich geöffnet mit Kennzahlen/JSON.

**Hinweis:** In dieser Ausführung wurden keine Browser-Screens automatisch erzeugt; die Dateien bitte nach manuellem Check ergänzen.

---

## 6. Bekannte offene Punkte

- **[FUTURE]** End-to-End- oder Playwright-Test für die vollständige Seitenstruktur.
- **[TECHNICAL_DEBT]** Einige Rationale-/Listen-Texte aus `signal-rationale` können weiterhin technische Begriffe enthalten — getrennt von der neuen Kurzfassung.
