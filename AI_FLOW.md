# KI-Strecke: Operator Explain (End-to-End)

Dieses Dokument beschreibt die **verifizierte** Kette vom Dashboard bis zur strukturierten LLM-Antwort. Es geht um **einen** konkreten, produktionsnahen Pfad — nicht um alle LLM-Features im Repo.

## Kurzüberblick

| Schicht                     | Rolle                                                       |
| --------------------------- | ----------------------------------------------------------- |
| UI                          | Formular „Frage ans Modell“ auf der Health-Konsole          |
| BFF (Next.js Route Handler) | Session/Gateway-Auth, Proxy zum API-Gateway                 |
| API-Gateway                 | JWT (`gateway:read`), Audit, Forward mit `INTERNAL_API_KEY` |
| LLM-Orchestrator            | Retrieval, Schema-Validation, Provider (OpenAI oder Fake)   |
| Anzeige                     | `explanation_de`, Provider-Zeile, bei Fake: Warnbanner      |

## Request-Fluss (Reihenfolge)

1. **Browser** `POST /api/dashboard/llm/operator-explain`  
   Body: `{ question_de, readonly_context_json }`  
   Datei: `apps/dashboard/src/app/api/dashboard/llm/operator-explain/route.ts`

2. **BFF** prüft Operator-Gateway-Auth (`requireOperatorGatewayAuth`), baut `Authorization: Bearer …` und ruft  
   `POST {API_GATEWAY_URL}/v1/llm/operator/explain`  
   (Timeout ~125 s)

3. **API-Gateway** `POST /v1/llm/operator/explain`  
   Datei: `services/api-gateway/src/api_gateway/routes_llm_operator.py`  
   Forward: `services/api-gateway/src/api_gateway/llm_orchestrator_forward.py` →  
   `POST {LLM_ORCH_BASE_URL}/llm/analyst/operator_explain`  
   Header: `X-Internal-Service-Key: {INTERNAL_API_KEY}`

4. **LLM-Orchestrator** `POST /llm/analyst/operator_explain`  
   Datei: `services/llm-orchestrator/src/llm_orchestrator/api/routes.py`  
   Service: `LLMService.run_operator_explain` → `run_structured` mit Schema  
   `shared/contracts/schemas/operator_explain.schema.json`

5. **Antwort** JSON-Envelope mit u. a. `ok`, `provider`, `model`, `result` (schema-konform), `provenance`.

6. **UI** parst JSON, validiert Mindestinhalt (`explanation_de` nicht leer), zeigt Text und optional Fake-Banner.  
   Dateien: `apps/dashboard/src/components/panels/OperatorExplainPanel.tsx`,  
   `apps/dashboard/src/lib/operator-explain-errors.ts`  
   **Observability:** BFF setzt/weiterleitet `X-Request-ID` / `X-Correlation-ID` zum Gateway; Orchestrator spiegelt dieselben IDs in Logs (`corr_*` bei `LOG_FORMAT=json`). Siehe `OBSERVABILITY_AND_SLOS.md`.

## UI-Einstieg

- **Route:** Operator-Konsole → **Health** (Seite mit Systemzustand).
- **Komponente:** `OperatorExplainPanel` — Abschnitt „Frage ans Modell“.

## Technischer Endpunkt (Server-seitig)

- **Öffentlich über Gateway:** `POST /v1/llm/operator/explain` (mit JWT).
- **Intern (Orchestrator):** `POST /llm/analyst/operator_explain` (mit internem Service-Key, falls konfiguriert).

## Provider: echt vs. Fake

| Modus                 | ENV (Orchestrator)                                                      | Verhalten                                                                                                             |
| --------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Fake (Smoke / CI)** | `LLM_USE_FAKE_PROVIDER=true`                                            | Kein OpenAI-Aufruf. Deterministische, schema-konforme Antwort; Operator-Explain-Text beginnt mit `[TEST-PROVIDER …]`. |
| **OpenAI**            | `LLM_USE_FAKE_PROVIDER=false` (oder unset) und `OPENAI_API_KEY` gesetzt | Echter Provider-Aufruf über die Orchestrator-Provider-Kette.                                                          |

Fake ist **explizit** im UI gekennzeichnet (`provider === "fake"` → Warnbanner) und im generierten Text.

## Relevante Dateien (Checkliste)

- UI: `apps/dashboard/src/components/panels/OperatorExplainPanel.tsx`
- BFF: `apps/dashboard/src/app/api/dashboard/llm/operator-explain/route.ts`
- Gateway: `services/api-gateway/src/api_gateway/routes_llm_operator.py`, `llm_orchestrator_forward.py`
- Orchestrator: `services/llm-orchestrator/src/llm_orchestrator/api/routes.py`, `service.py`
- Fake: `services/llm-orchestrator/src/llm_orchestrator/providers/fake_provider.py`
- Schema: `shared/contracts/schemas/operator_explain.schema.json`
- Tests: `tests/llm_orchestrator/test_structured_fake_provider.py`
- Skript: `scripts/verify_ai_operator_explain.py`

## ENV-Abhängigkeiten

### Dashboard (BFF)

- `API_GATEWAY_URL` — Basis-URL des Gateways
- `DASHBOARD_GATEWAY_AUTHORIZATION` — `Bearer <JWT>` mit Scope `gateway:read` (siehe `scripts/mint_dashboard_gateway_jwt.py`)

### API-Gateway

- `INTERNAL_API_KEY` — muss mit dem Orchestrator-`service_internal_api_key` übereinstimmen
- `LLM_ORCH_BASE_URL` oder ableitbar aus `HEALTH_URL_LLM_ORCHESTRATOR` (siehe Forward-Modul)

### LLM-Orchestrator

- `INTERNAL_API_KEY` / interner Key in Settings (gleicher Wert wie Gateway)
- `REDIS_URL` (Cache / Bus, je nach Setup)
- `LLM_USE_FAKE_PROVIDER=true` für deterministischen Test ohne OpenAI
- `OPENAI_API_KEY` für echtes Modell (wenn Fake aus)

## Verifikation

### 1) Automatisierter Unit-/Integrationstest (ohne laufende Dienste)

```bash
pytest tests/llm_orchestrator/test_structured_fake_provider.py::test_analyst_hypotheses_and_operator_explain -v
```

Prüft: HTTP 200, `provider == fake`, `execution_authority == none`, Erklärung enthält `[TEST-PROVIDER`.

### 2) Laufender Orchestrator (direkt)

```bash
# Orchestrator mit LLM_USE_FAKE_PROVIDER=true starten, dann:
python scripts/verify_ai_operator_explain.py --env-file .env.local --mode orchestrator
```

### 3) Volle Kette über Gateway

```bash
# Gateway + Orchestrator laufen; JWT in .env.local
python scripts/verify_ai_operator_explain.py --env-file .env.local --mode gateway
```

### 3b) Staging-/Pre-Prod (Health + System + dieser KI-Pfad)

```bash
python scripts/staging_smoke.py --env-file .env.shadow
# optional: keine Loopback-Gateway-URL
python scripts/staging_smoke.py --env-file .env.shadow --disallow-loopback-gateway
```

Siehe `STAGING_PARITY.md`.

### 4) Manuell im UI

1. Stack starten (Dashboard, Gateway, Orchestrator; ENV wie oben).
2. Als Operator einloggen, **Health** öffnen.
3. Frage eingeben (≥ 3 Zeichen), optional JSON-Kontext, „Frage senden“.
4. Erwartung: strukturierter Text unterhalb des Formulars; bei Fake: gelber Hinweis „Test-Provider“ und Text mit `[TEST-PROVIDER`.

## Fehlerpfad (nachvollziehbar)

- **401** am BFF/Gateway: fehlende oder abgelaufene Session / JWT.
- **503** mit `LLM_ORCH_UNAVAILABLE`: Gateway kann Orchestrator-URL/Key nicht nutzen.
- **502** / Orchestrator: fehlender `OPENAI_API_KEY` wenn Fake nicht aktiv — ehrliche Upstream-Meldung; UI mappt über `operator-explain-errors.ts` auf verständliche Texte.

## Kein „Demo-Schein“

Diese Strecke liefert entweder eine **schema-validierte** Antwort vom Orchestrator (Fake oder OpenAI) oder einen **HTTP-Fehler** mit strukturiertem `detail` — keine statische Hardcode-Antwort im Dashboard-Code.

---

## Zweite verifizierte Strecke: Strategie-Signal-Erklaerung

| Schicht      | Rolle                                                          |
| ------------ | -------------------------------------------------------------- |
| UI           | Panel auf **Signaldetail** (`/console/signals/[id]`)           |
| BFF          | `POST /api/dashboard/llm/strategy-signal-explain`              |
| Gateway      | `POST /v1/llm/operator/strategy-signal-explain`                |
| Orchestrator | `POST /llm/analyst/strategy_signal_explain`                    |
| Schema       | `shared/contracts/schemas/strategy_signal_explain.schema.json` |

**Eingabe:** `signal_context_json` (Objekt, typ. Signal-Snapshot) und optional `focus_question_de` (≥ 3 Zeichen). Mindestens eines: nicht-leerer Snapshot **oder** Fokusfrage.

**Antwort:** `result.strategy_explanation_de`, `risk_and_caveats_de`, `referenced_input_keys_de`, `non_authoritative_note_de`; `execution_authority` immer `none`.

**Verifikationsskript:** `python scripts/verify_ai_strategy_signal_explain.py --env-file .env.local --mode orchestrator` bzw. `--mode gateway`.

**Tests:** `pytest tests/llm_orchestrator/test_structured_fake_provider.py::test_analyst_hypotheses_and_operator_explain`, `pytest tests/unit/api_gateway/test_routes_llm_operator.py` (inkl. `test_strategy_signal_explain_*`).
