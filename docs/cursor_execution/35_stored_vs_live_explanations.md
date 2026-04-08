# 35 — Signaldetail: gespeicherte vs. deterministische vs. Live-KI-Erklärungen

## Ziel

Klare **Layer-Architektur** auf dem Signaldetail (`console/signals/[id]`): Nutzer erkennen sofort, was aus der **Explain-API/DB**, was **deterministisch (Engine/Signalzeile)** und was **live per LLM** kommt — ohne sprachliche oder visuelle Vermischung.

Referenzen: `docs/chatgpt_handoff/06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md`, `docs/cursor_execution/15_signal_engine_and_signal_contracts.md`.

## Finale UI-Reihenfolge (Lesepfad)

1. **Kontext-Chart** (Marktdaten; optional KI-Overlays nur nach Strategy-Signal-Explain).
2. **Übersicht** — Kennzahlen aus `GET /v1/signals/{id}` (technische Tabelle).
3. **Erklärungen zu diesem Signal** (Einleitungstext).
4. **Schritt 1 — Kurzfassung** — `explain_short` aus `GET /v1/signals/{id}/explain`. Badge: **Gespeichert (DB/Explain-API)**.
5. **Schritt 2 — Gespeicherte Facherklärung** — `explain_long_md` (Markdown), optional Hinweis aus `explanation_layers.persisted_narrative.note_de`. Gleiches Badge „Gespeichert“.
6. **Risikowarnungen** — `risk_warnings_json` aus Explain-Payload (`RiskWarningsPanel`).
7. **Schritt 3 — Deterministische Engine-Gründe** — Lesbare Liste aus `reasons_json` via `summarizeReasonsJsonForUi`, darunter `<details>` mit vollem JSON. Badge: **Deterministisch (Engine JSON)**.
8. **Vertrags-Hinweise** — `explanation_layers` als Aufzählung (Metadaten/Definition laut API), plus `signal_contract_version`.
9. **Kompakt-Spiegelung** — „Warum kein Trade?“ / „Warum genau dieser Trade?“ aus **Signalzeile** (`summarizeNoTradeReasons` / `summarizeTradeRationale`). Badge: **Spiegelung Signalzeile** (von `reasons_json` zu unterscheiden).
10. **Schritt 4 — Live-KI** — `StrategySignalExplainPanel` in abgesetztem Rahmen mit Badge **Live-KI (nicht gespeichert)**; Titel/Lead betonen On-Demand und Nicht-Persistenz.

Darunter: übrige Audit-Panels (Instrument, Stop-Budget, …) unverändert.

## API-Nachweise

| Pfad                           | Inhalt für die Ebenen                                                                                                     |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/signals/{id}`         | Flache Signalzeile für Spiegelung & LLM-Snapshot                                                                          |
| `GET /v1/signals/{id}/explain` | `explain_short`, `explain_long_md`, `reasons_json`, `risk_warnings_json`, `explanation_layers`, `signal_contract_version` |

**Strategy-Signal-Explain:** `POST /api/dashboard/llm/strategy-signal-explain` → Gateway → Orchestrator — **separater** Pfad; ersetzt keine Explain-DB-Felder.

## Beispieltexte (sachlich)

- **Schritt 1 (Kurzfassung):** z. B. ein Satz aus `explain_short` wie „Long-Bias im 5m-Regime, Hebel durch Risk-Governor begrenzt.“ — stammt aus Persistenz, nicht aus Live-LLM.
- **Schritt 2 (Markdown):** längerer erklärender Text in `explain_long_md`.
- **Schritt 3:** Stichpunkte aus `reasons_json` (z. B. Engine-Codes/Messages); Roh-JSON in ausklappbarem Block.
- **Schritt 4:** Antwort des Modells nach Klick auf „Erklärung anfordern“ — mit `non_authoritative_note_de` im Ergebnis-View.

## Implementierung (Repo)

| Teil                      | Pfad                                                                                          |
| ------------------------- | --------------------------------------------------------------------------------------------- |
| Seitenlogik & Reihenfolge | `apps/dashboard/src/app/(operator)/console/signals/[id]/page.tsx`                             |
| reasons_json → Zeilen     | `apps/dashboard/src/lib/signal-explain-display.ts`                                            |
| Styles                    | `apps/dashboard/src/app/globals.css` (`.signal-explain-layer`, `.signal-explain-llm-wrap`, …) |
| i18n                      | `apps/dashboard/src/messages/de.json`, `en.json` (`pages.signalsDetail.*`)                    |
| Test                      | `apps/dashboard/src/lib/__tests__/signal-explain-display.test.ts`                             |

## UI-Nachweis (manuell)

1. Signaldetail öffnen: erste Erklärboxen direkt **unter** der Übersicht, **vor** Instrument/Persistenz-Blöcken.
2. Badges: grün „Gespeichert“ bei Schritt 1–2, gelb „Engine“ bei Schritt 3, Live-Bereich mit **Live-KI**-Badge.
3. Tab „Erklärung anfordern“ nur im unteren LLM-Kasten; Chart-Overlays weiterhin an Strategy-Signal-Explain gekoppelt.

## Tests

```text
cd apps/dashboard
pnpm check-types
pnpm test -- src/lib/__tests__/signal-explain-display.test.ts --runInBand
```

## Offene Punkte

- **[FUTURE]** Übersichts-Panel teilweise noch fest deutsch beschriftet — gesonderte i18n-Runde möglich.
- **[RISK]** Leere `reasons_json` / fehlende Explain-Zeile: UI zeigt Platzhalter bzw. „Explain-API nicht verfügbar“; fachlich mit Ops klären.
