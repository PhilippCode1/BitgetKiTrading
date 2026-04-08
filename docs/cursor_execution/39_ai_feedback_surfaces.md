# Task 39 — KI-gestützte Diagnose-Rückmeldungen (Oberflächen)

## Ziel

Strukturierte, längere aber lesbare Hinweise bei degradierten oder kaputten Zuständen (Charts leer, Terminal stale/leer, Health-Ladefehler, LLM-Fehler, eskalierte Alerts), angelehnt an **docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md** und die **Safety-AI** aus **docs/cursor_execution/38_safety_ai_architecture.md** (Endpunkt `safety-incident-diagnose`, Panel `SafetyDiagnosisPanel`).

## Bausteine

| Baustein                                                        | Pfad                                                                         |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Deterministische Szenario-Logik                                 | `apps/dashboard/src/lib/surface-diagnostic-catalog.ts`                       |
| UI-Karte (Ursachen, Dienste, Schnittstellen, Schritte)          | `apps/dashboard/src/components/diagnostics/SurfaceDiagnosticCard.tsx`        |
| Einklappbare Safety-KI mit Overlay                              | `apps/dashboard/src/components/diagnostics/SafetyDiagnosisInline.tsx`        |
| Health: Ladefehler ohne doppeltes Safety-Panel                  | `apps/dashboard/src/components/diagnostics/HealthLoadFailureSurfaceCard.tsx` |
| Health: eskalierte offene Alerts                                | `apps/dashboard/src/components/diagnostics/HealthOpenAlertsSurfaceBlock.tsx` |
| Safety-Panel: `initialQuestionDe`, `embedded`, `contextOverlay` | `apps/dashboard/src/components/panels/SafetyDiagnosisPanel.tsx`              |

Texte: `diagnostic.surfaces.*` in `apps/dashboard/src/messages/de.json` und `en.json` (Patch-Skript: `scripts/patch_diagnostic_i18n.mjs`).

## Eingebundene Flächen (≥ 3)

1. **Konsole — Marktchart** (`ConsoleLiveMarketChartSection`): Fetch-Fehler, leere Kerzen, schlechte `market_freshness` (stale/dead/no_candles).
2. **Live-Terminal** (`LiveTerminalClient`): Fetch-Fehler, SSE stale, leere Kerzen, schlechte Frische.
3. **Health** (`health/page.tsx`): Sammelladefehler + strukturierte Karte; bei Fehler **vorausgefüllte** Sicherheitsfrage im großen `SafetyDiagnosisPanel` (Kontext enthält `dashboard_load_error`). Zusätzlich **Monitor-Alerts**: Block unter der Tabelle, wenn mindestens ein offener Alert mit eskalierender Severity (z. B. high/critical/error).
4. **Operator-Erklär-KI** (`OperatorExplainPanel`): bei fehlgeschlagenem LLM-Call strukturierte Karte + einklappbare Safety-KI.

## UI-Nachweise (kaputt / degraded)

| Szenario                | Wo auslösen                                                                                               | Erwartete Karte (Titel-Ausschnitt)                                |
| ----------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Chart ohne Daten        | Symbol/TF wählen, für das der Live-State **0 Kerzen** liefert (oder Stack ohne Ingest)                    | „Konsole: Marktchart — keine Kerzen“                              |
| Chart-Fetch-Fehler      | BFF/Gateway stoppen oder ungültige Session                                                                | „Konsole: Marktchart — Abruf fehlgeschlagen“                      |
| Terminal SSE stale      | Stack so betreiben, dass Stream ruhig bleibt (oder `diagnostic=1` + künstlich lange Pause); Badge „ruhig“ | „Live-Terminal: Echtzeit-Stream ruhig (stale)“                    |
| Health-Ladefehler       | Einen der drei Health-Fetches brechen (Gateway down)                                                      | „Health-Seite: Sammelladefehler“ + Hinweis auf Safety-Panel unten |
| Eskalierte Alerts       | Offene Alerts mit Severity `high` / `critical` / `error`                                                  | „Monitor: eskalierte offene Alerts“                               |
| operator-explain Fehler | Anfrage senden bei Provider-Ausfall / Timeout                                                             | „Operator-Erklär-KI: Anfrage fehlgeschlagen“                      |

## Tests

- `apps/dashboard/src/lib/__tests__/surface-diagnostic-catalog.test.ts` — Prioritäten und Eskalations-Erkennung.
- Typen: `pnpm check-types` (Repo-Root).

## Beispiel Safety-Fragen (Auszug)

- Health-Ladefehler (automatisch im großen Panel): Schlüssel `diagnostic.surfaces.healthPageLoadFailed.suggestedSafetyQuestion`.
- Oberflächen mit einklappbarer KI: jeweils `*.suggestedSafetyQuestion` unter dem passenden `diagnostic.surfaces.*` Key.

## Offene Punkte

- `[FUTURE]` Weitere Flächen (z. B. Shadow-Live, Signal-Detail) können dieselbe Karte + Katalog-Einträge nutzen.
- `[RISK]` Safety-AI bleibt **indikativ**; die statische Karte liefert die belastbare Checkliste, die KI vertieft optional.
