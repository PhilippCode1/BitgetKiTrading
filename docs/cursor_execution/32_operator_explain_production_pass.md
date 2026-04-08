# 32 — Operator Explain: Production Pass (Health → BFF → Gateway → Orchestrator)

## Ziel

Die Strecke **Operator Explain** (Health-Seite) soll technisch stabil und ruhig nutzbar sein: klare Grenzen für Kontext-JSON, verständliche Fehler- und Ladezustände, nachvollziehbare **Provenance** (inkl. Prompt-/Governance-Versionen), Gateway-**Audit** mit Kontextmetriken (ohne Payload-Inhalt), sowie abgesicherte Tests und ein reproduzierbarer E2E-Nachweis.

Referenzen: `docs/chatgpt_handoff/06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md`, `AI_FLOW.md`.

## End-to-End-Kette (kurz)

1. **Browser:** `OperatorExplainPanel` → `POST /api/dashboard/llm/operator-explain` (Next.js BFF).
2. **BFF:** `apps/dashboard/src/app/api/dashboard/llm/operator-explain/route.ts` — Auth, Fragenlänge, Objekt-Check für `readonly_context_json`, **UTF-8-Byte-Limit** (`OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES` = 24_000) → bei Überschreitung **400** mit `detail.code: CONTEXT_JSON_TOO_LARGE`.
3. **Gateway:** `POST {API_GATEWAY_URL}/v1/llm/operator/explain` — JWT (`require_sensitive_auth`), **Audit** `llm_operator_explain` mit `extra`: `question_len`, `context_key_count`, `context_top_keys` (max. 24 Keys, keine Werte).
4. **Orchestrator:** `POST …/llm/analyst/operator_explain` — strukturierte Antwort, Schema `shared/contracts/schemas/operator_explain.schema.json`, **provenance** u. a. `task_type`, `prompt_manifest_version`, `prompt_task_version`.

## UX / Fehlerabbildung (Dashboard)

- **`apps/dashboard/src/lib/operator-explain-errors.ts`:** `extractDetailFields` liest `detail` und verschachteltes `error`-Objekt (Gateway-Produktions-Envelope), inkl. **`failure_class`**. `resolveOperatorExplainFailure` mappt u. a. `CONTEXT_JSON_TOO_LARGE`, `circuit_open`, `no_provider_configured`, `retry_exhausted`. `resolveNetworkFailure` erkennt u. a. **`econnrefused`** (Kleinschreibung).
- **i18n:** `apps/dashboard/src/messages/de.json`, `en.json` — einheitliche Lead-/Hint-Texte, neue Fehlertasten, `ui.llmAnswer.metaGovernance`.
- **UI:** `OperatorExplainPanel.tsx` — `maxLength` und Zeichenzähler für Kontext, Vorab-Checks (Textlänge + JSON-Bytes vs. BFF-Limit). `LlmStructuredAnswerView.tsx` — optionale Zeile **Prompt & Governance** aus Provenance.

## Kontext-Limits (geteilt)

- **`apps/dashboard/src/lib/operator-explain-context.ts`:** `OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES`, `OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS`, Hilfsfunktion `readonlyContextJsonUtf8ByteLength`.

## Tests (ausgeführt)

```text
# Repo-Root (PowerShell)
Set-Location <repo>
python -m pytest tests/unit/api_gateway/test_routes_llm_operator.py -q --tb=no
# Ergebnis (lokal): 5 passed

Set-Location apps\dashboard
pnpm test -- src/lib/__tests__/operator-explain-errors.test.ts --runInBand
# Ergebnis (lokal): 19 passed
```

`test_operator_explain_returns_upstream_payload` prüft nun die **Audit-Extra-Felder** (`context_key_count`, `context_top_keys`). `operator-explain-errors.test.ts` deckt `failure_class`, verschachteltes `error`, `CONTEXT_JSON_TOO_LARGE` und `ECONNREFUSED` ab.

## E2E-Nachweis (Skript)

```text
# Orchestrator direkt (INTERNAL_API_KEY / Fake-Provider siehe AI_FLOW.md)
python scripts/verify_ai_operator_explain.py --env-file .env.local --mode orchestrator

# Vollständiger Pfad über Gateway (JWT)
python scripts/verify_ai_operator_explain.py --env-file .env.local --mode gateway
```

**Anpassung in diesem Pass:** Bei Transportfehlern (z. B. Orchestrator nicht gestartet) beendet das Skript mit **Exit 1** und der Meldung `FAIL transport: …` **ohne Python-Traceback**.

**Lauf in dieser Umgebung (Orchestrator nicht erreichbar):**

```text
=== verify_ai_operator_explain ===
mode=orchestrator
…
FAIL transport: [WinError 10061] … Verbindung verweigerte
```

Exit-Code: 1 (erwartet, bis Dienste laufen).

Zusätzlich laut `AI_FLOW.md`: `pytest tests/llm_orchestrator/test_structured_fake_provider.py::test_analyst_hypotheses_and_operator_explain -v` für den Orchestrator mit Fake-Provider.

## Betroffene Dateien (Überblick)

| Bereich            | Pfad                                                                                          |
| ------------------ | --------------------------------------------------------------------------------------------- |
| Gateway-Audit      | `services/api-gateway/src/api_gateway/routes_llm_operator.py`                                 |
| Gateway-Tests      | `tests/unit/api_gateway/test_routes_llm_operator.py`                                          |
| BFF                | `apps/dashboard/src/app/api/dashboard/llm/operator-explain/route.ts` (bereits mit Byte-Limit) |
| Kontext-Konstanten | `apps/dashboard/src/lib/operator-explain-context.ts`                                          |
| Fehler-Mapping     | `apps/dashboard/src/lib/operator-explain-errors.ts`                                           |
| Fehler-Tests       | `apps/dashboard/src/lib/__tests__/operator-explain-errors.test.ts`                            |
| UI                 | `OperatorExplainPanel.tsx`, `LlmStructuredAnswerView.tsx`                                     |
| i18n               | `apps/dashboard/src/messages/de.json`, `en.json`                                              |
| Verifikation       | `scripts/verify_ai_operator_explain.py`                                                       |

## Bekannte offene Punkte

- **[RISK]** E2E-Skript und manuelle Health-UI-Prüfung erfordern laufende Dienste; ohne Stack kein `exit 0` des Skripts.
- **[FUTURE]** Optional: dedizierte Playwright-/E2E-Tests für das BFF-Posting aus dem Browser, wenn die Suite dafür ausgebaut wird.

## Erledigt-Definition (dieser Pass)

- Operator Explain: Validierung (Client + BFF + Gateway-Weiterleitung), verständliche Fehler/Ladezustände/Provider-Hinweise, Provenance-Anzeige und Audit-Metriken.
- Pytest- und Jest-Befehle oben grün; Nachweisdatei beschreibt Kette, Tests und Skript.
