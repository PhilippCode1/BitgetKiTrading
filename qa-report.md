# QA-Durchgang — Operator-Assistent (KI) & Nutzererfahrung

Stand: Qualitaetspass nach Prompt 9, fokussiert auf die **erste echte KI-Strecke** (Operator Explain auf `/console/health`) und stabile Fehler-/Ladezustaende.

**Gesamtstatus & Release:** `PRODUCT_STATUS.md`, `release-readiness.md` · **Technik KI:** `ai-architecture.md`

## Geprüfte Szenarien (manuell / logisch abgedeckt)

| Thema                                                          | Massnahme                                                                                                                                      |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Leere / zu kurze Frage**                                     | Client-Validierung (≥3 Zeichen), Zeichenzähler, max. 8000 Zeichen.                                                                             |
| **Ungültiger JSON-Kontext**                                    | Klare Meldungen; kein Request bei Parse-Fehler.                                                                                                |
| **Doppelklick / parallele Submits**                            | `submitLockRef` blockiert zweiten Lauf bis der erste beendet ist.                                                                              |
| **Langsame Antwort**                                           | Sekundenzähler „{n}s vergangen“ während des Laufs; Timeout clientseitig ~128s mit eigener Meldung.                                             |
| **Abbruch während Laden**                                      | Button „Anfrage abbrechen“; `AbortController`; bei Navigation **kein** Fehler-Toast (Teardown unterscheidet User-Abbruch / Timeout / Unmount). |
| **Fehlende Konfiguration**                                     | HTTP-Status + JSON werden auf **verständliche** Texte gemappt (Gateway/Orchestrator, `OPENAI_API_KEY`, BFF-JWT, Offline).                      |
| **Serverfeiler / HTML-Fehlerseiten**                           | Erkennung HTML-Antwort; generische sichere Meldung statt Rohtext.                                                                              |
| **Ungültige KI-Antwort (200, aber ohne brauchbare Erklärung)** | `isOperatorExplainSuccessPayload`: verlangt nicht-leeres `explanation_de`; sonst Meldung „nicht interpretierbar“.                              |
| **Schlechtes Netz**                                            | `resolveNetworkFailure` für typische Browser-Meldungen („Failed to fetch“).                                                                    |
| **Mobile**                                                     | CSS: umbrechende Button-Zeile, volle Breite unter 640px, min. 44px Touch-Höhe, `overflow-wrap` für lange Antworten.                            |

## Technische Verbesserungen

- **`operator-explain-errors.ts`**: zentrale Zuordnung Status/Code → i18n, `sanitizePublicErrorMessage` gegen lange Rohfehler.
- **`OperatorExplainPanel`**: `React.memo`, keine `AbortSignal.timeout`-Kollision mit User-Abort; `mountedRef`/`teardownRef` vermeidet **setState nach Unmount**.
- **Performance (gezielt)**: Memo des Panels; kein zusätzlicher globaler Context-Consumer; ein Request pro Aktion; Intervall nur bei `loading`.

## Automatisierte Tests

```bash
cd apps/dashboard && pnpm test -- src/lib/__tests__/operator-explain-errors.test.ts src/lib/__tests__/api-error-detail.test.ts --runInBand
```

Gateway-Route (Forward gemockt) bleibt wie zuvor: `python -m pytest tests/unit/api_gateway/test_routes_llm_operator.py -q`

## Bewusst nicht verschoben

- Kein generelles Refactoring anderer Console-Seiten.
- Kein Debounce auf Tastatur (nur ein Submit-Trigger pro Klick).
- Schwache Netzwerke mit Retry-Backoff nur implizit (Nutzer nutzt „Erneut versuchen“).

## Kurzfazit

Die KI-Oberfläche soll **nicht still scheitern**: Ladezustand sichtbar, Abbruch möglich, typische Konfigurations- und Netzfehler in **Klartext** (DE/EN), technische Details nur gekürzt oder gar nicht in der UI.
