# Main Console KI-Operator-Assistent (Deutsch, nicht-ausfuehrend)

## Ziel

Der KI-Assistent hilft Philipp beim Verstehen von Systemzustand, Incident-Lage
und Risk-Gruenden. Er ist strikt **read-only** und darf keine Trading-Freigaben
oder Gate-Entscheidungen ersetzen.

## Erlaubte Aufgaben

1. Systemstatus auf Deutsch erklaeren.
2. Live-Blocker zusammenfassen.
3. Risk-Governor-Gruende erklaeren.
4. Asset-Blockgruende erklaeren.
5. Reconcile-Fail verstaendlich beschreiben.
6. Shadow-Burn-in-Report einordnen.
7. Fehlerzustaende sortieren.
8. Naechste sichere technische Pruefschritte vorschlagen.
9. Relevante Doku verlinken.
10. Nur erklaeren, nie ausfuehren.

## Verbotene Aufgaben

1. Keine Live-Freigabe.
2. Kein Risk-Gate-Override.
3. Kein Kill-Switch-Release.
4. Kein Safety-Latch-Release.
5. Keine Order-Erzeugung.
6. Keine Anlageberatung.
7. Keine Gewinnversprechen.
8. Keine Secret-Verarbeitung oder Ausgabe.
9. Keine Ausgabe von API-Keys/Tokens/Passphrases.
10. Kein "System ist sicher", wenn Evidence fehlt.

## Safety-Contract

- Strukturierte Antworten muessen `execution_authority="none"` enthalten.
- Jede sichtbare Antwort muss klar nicht-autoritativ sein (keine Live-Freigabe).
- Fehlende Daten werden als fehlend/unknown benannt, niemals halluziniert als OK.
- LLM-Ausfall schaltet nur Erklaerung auf degraded, nie Trading auf allow.
- Fake-Provider gilt nur als Testmodus, nicht als Produktions-Evidence.
- Secret-Redaction vor LLM-Aufruf ist Pflicht.

## Verdrahtung (bestehende sichere Pfade)

- BFF Route Operator Explain: `apps/dashboard/src/app/api/dashboard/llm/operator-explain/route.ts`
- BFF Route Safety Diagnose: `apps/dashboard/src/app/api/dashboard/llm/safety-incident-diagnose/route.ts`
- UI Panels: `OperatorExplainPanel.tsx`, `SafetyDiagnosisPanel.tsx`, `LlmStructuredAnswerView.tsx`

## Degraded-Fallback

Wenn LLM-Orchestrator/Provider nicht erreichbar ist, zeigt die UI:

`KI-Erklärung aktuell nicht verfügbar — keine Auswirkung auf Trading-Freigaben.`

Dieser Zustand veraendert keine Gates und keine Live-Freigaben.
