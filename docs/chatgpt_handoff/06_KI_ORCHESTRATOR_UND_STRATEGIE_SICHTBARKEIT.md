# KI: Orchestrator und Strategie-Sichtbarkeit (bitget-btc-ai)

**Zweck:** ChatGPT soll nach dem Lesen **exakt** wissen, welche LLM-Funktionen im Repo **real** existieren, welche nur **vorbereitet** sind, wie sie von OpenAI vs. Fake-Provider getrennt werden, und was im Frontend als „KI“ erscheint — **ohne** Marketing.

**Kennzeichnung:** `verifiziert (Repo)` = aus Code/Doku nachvollziehbar; `verifiziert (Tests diese Session)` = Befehl ausgeführt, Exit 0; `nicht verifiziert (Laufzeit)` = braucht laufenden Stack/Keys.

---

## 1. Management-Zusammenfassung

**Brutal ehrlich:** Es gibt **keine** im Repo verifizierbare, vollautonome „Trading-KI“, die Märkte handelt oder Orders freigibt. Die **Kern-Signal-Entscheidung** ist **deterministisch** (Signal-Engine, Regeln, Scores) — im Code ausdrücklich **ohne LLM** in der Kernkette (`decision_control_flow` u. a.).

**Was es wirklich gibt:**

1. **LLM-Orchestrator** (`services/llm-orchestrator`): einziger Dienst, der **OpenAI** (structured output) oder den **Fake-Provider** nutzt. Interne Authentifizierung: `X-Internal-Service-Key` / `INTERNAL_API_KEY`.
2. **Zwei produkt-sichtbare, stateless Structured-Output-Strecken** fürs Dashboard: **Operator Explain** und **Strategie-/Signalerklärung** — jeweils Gateway → Orchestrator, `execution_authority` im JSON-Schema **fest `none`** (keine Orderhoheit).
3. **Assist-Schicht (Multi-Turn):** Orchestrator `POST /llm/assist/turn` mit **Konversations-Speicher** (Redis, TTL); Gateway `/v1/llm/assist/{segment}/turn`; Dashboard-BFF `/api/dashboard/llm/assist/[segment]`. UI: **`AssistLayerPanel`** auf **Health** (Tabs Admin/Strategy) und **Account** (Onboarding/Billing) — **nicht** dasselbe UI wie Operator Explain.
4. **Persistente Signalerklärungen aus der DB:** `GET /v1/signals/{id}/explain` liefert **gespeicherte** Felder (`explain_short`, `explain_long_md`, …) — **kein** garantierter Live-LLM-Aufruf beim Seitenaufruf; Herkunft kann Engine-Pipeline sein, nicht die beiden Dashboard-LLM-Formulare.

**Was es nicht gibt (Ist-Stand Repo):** Freier Produkt-Chat über alle Themen; persistente Chat-Historie für **Operator Explain**; Dashboard-Anbindung für jeden weiteren Orchestrator-Endpunkt; LLM-gesteuerte Chart-Overlays **ohne** dass der Nutzer zuerst die Strategie-Signal-Erklärung anfordert und das Modell `chart_annotations` liefert.

---

## 2. Vollständige KI-Landkarte des Projekts

### 2.1 Zentrale LLM-Laufzeit

| Komponente           | Rolle                                                                                                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **llm-orchestrator** | OpenAI oder Fake; Schemas unter `shared/contracts/schemas/*.schema.json`; Retrieval aus `docs/llm_knowledge`; Redis-Cache, Circuit Breaker; Assist-Conversation-Store |
| **api-gateway**      | Öffentliche `/v1/llm/*`-Routen mit JWT (`require_sensitive_auth` o. ä. je Route); Forward mit `INTERNAL_API_KEY`; Audit-Zeilen                                        |
| **dashboard BFF**    | `POST /api/dashboard/llm/operator-explain`, `…/strategy-signal-explain`, `…/llm/assist/[segment]` — trägt `DASHBOARD_GATEWAY_AUTHORIZATION`                           |
| **dashboard UI**     | `OperatorExplainPanel`, `StrategySignalExplainPanel`, `AssistLayerPanel`, `LlmStructuredAnswerView`; Signaldetail-Chart mit optionalem KI-Layer                       |

### 2.2 KI oder LLM **außerhalb** der beiden Haupt-Strecken (indirekt)

| Erscheinung                             | Natur                                                                                                                                                                                                                         |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Signal-Engine / Risk / News-Scoring** | Überwiegend **deterministisch**; News kann LLM-Deltas in Regeln erwähnen — **nicht** gleichbedeutend mit den Dashboard-LLM-Panels                                                                                             |
| **`/v1/signals/{id}/explain`**          | **Datenbank-Lesepfad** (`app.signal_explanations` o. ä. via `fetch_signal_explain`) — „Erklärung“ kann früher von einem LLM oder anderer Logik geschrieben worden sein, die UI macht dabei **keinen** neuen Orchestrator-Call |
| **Admin LLM-Governance**                | Gateway-Forward zu Orchestrator `/llm/governance/summary` — **Operator-Dashboard-BFF nicht** identisch mit den zwei KI-Formularen; Zielgruppe/Auth admin                                                                      |
| **System-Health**                       | Zeigt u. a. Erreichbarkeit `llm-orchestrator` — **kein** Modell-Reasoning                                                                                                                                                     |
| **Learning-/Drift-Reports**             | Statistik/Metriken; **kein** generisches LLM-Panel dafür im Sinne von `ai-architecture.md`                                                                                                                                    |

`verifiziert (Repo):` `ai-architecture.md`, `PRODUCT_STATUS.md`, `routes_signals_proxy.py`, `routes_admin.py`.

### 2.3 Strategie-Registry vs. KI

- **`/v1/registry/strategies`:** Metadaten aus `learn.strategies` — **kein** LLM-Endpunkt.
- **Sichtbare „Strategie“ im Signal-UI:** Deterministische Spalten (`strategy_name`, Playbooks, Regime, …) aus `app.signals_v1` + gespeicherte Erklärungen + **optional** Live-Panel „Strategie-Signal-Erklaerung“ (LLM auf Knopfdruck).

---

## 3. Verifizierte LLM-End-to-End-Strecken

### 3.1 Operator Explain (stateless)

**Pfad:** Browser → `POST /api/dashboard/llm/operator-explain` → Gateway `POST /v1/llm/operator/explain` → Orchestrator `POST /llm/analyst/operator_explain`.

**Eingabe:** `question_de` (3–8000 Zeichen), optional `readonly_context_json` (nur Prompt-Kontext, **kein** serverseitiger Verlaufsspeicher laut `ai-architecture.md`).

**Ausgabe:** Envelope mit `result` gemäß `operator_explain.schema.json` (`explanation_de`, `referenced_artifacts_de`, `non_authoritative_note_de`, `execution_authority: "none"`).

**UI:** `console/health` — Panel **Operator Explain** (`OperatorExplainPanel.tsx`).

`verifiziert (Repo):` `ai-architecture.md`, `routes_llm_operator.py`, `operator-explain/route.ts`, `OperatorExplainPanel.tsx`.

### 3.2 Strategie-/Signalerklärung (stateless, mit optionalem Chart-Layer)

**Pfad:** Browser → `POST /api/dashboard/llm/strategy-signal-explain` → Gateway `POST /v1/llm/operator/strategy-signal-explain` → Orchestrator `POST /llm/analyst/strategy_signal_explain`.

**Eingabe:** `signal_context_json` (Snapshot vom Signal-Detail) und/oder `focus_question_de` (Gateway/BFF validieren: mindestens eines muss sinnvoll sein).

**Ausgabe:** `strategy_signal_explain.schema.json` inkl. optionalem `chart_annotations` (Linien, Bänder, Marker, Notizen) für `ProductCandleChart` — **nur** wenn UI `llmChartIntegration` aktiv ist (Signaldetail: `SignalDetailMarketChartBlock` + Context).

**UI:** `console/signals/[id]` — `StrategySignalExplainPanel`; Chart darüber mit KI-Layer-Toggle.

`verifiziert (Repo):` `StrategySignalExplainPanel.tsx`, `SignalDetailMarketChartBlock.tsx`, `strategy-signal-explain/route.ts`, `ProductCandleChart.tsx` (Kommentare zu `chart_annotations_v1`).

### 3.3 Assist Multi-Turn (Konversation)

**Pfad:** Browser → `POST /api/dashboard/llm/assist/{segment}` → Gateway `POST /v1/llm/assist/{segment}/turn` → Orchestrator `POST /llm/assist/turn`.

**Eingabe:** `conversation_id` (UUID), `user_message_de`, optional `context_json`.

**Segments (BFF-Allowlist):** `admin-operations`, `strategy-signal`, `customer-onboarding`, `support-billing`.

**UI:** `AssistLayerPanel` auf **Health** (erste zwei Segmente) und **Account** (letzte zwei).

**Wichtig:** Das ist **technisch** Multi-Turn (History im Orchestrator-Store), aber **kein** Ersatz für einen vollständigen „Produkt-Chat“ über alle Domänen und **nicht** dasselbe Produkt wie Operator Explain.

`verifiziert (Repo):` `assist/[segment]/route.ts`, `routes_llm_assist.py`, `llm_orchestrator/service.py` (`run_assistant_turn`), `AssistLayerPanel.tsx`.

---

## 4. Tabelle: Route, beteiligte Datei, Auth, Provider, Status

| Öffentliche Route (für Dashboard)                 | BFF / Gateway / Orchestrator                                                          | Auth (typisch)                                                                            | Provider                                                       | Status                                                                             |
| ------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `POST /api/dashboard/llm/operator-explain`        | → `/v1/llm/operator/explain` → `/llm/analyst/operator_explain`                        | BFF: `DASHBOARD_GATEWAY_AUTHORIZATION`; Gateway: sensibles JWT (`require_sensitive_auth`) | OpenAI oder Fake (`LLM_USE_FAKE_PROVIDER`) am **Orchestrator** | **Produktiv vorgesehen**; `verifiziert (Repo)`                                     |
| `POST /api/dashboard/llm/strategy-signal-explain` | → `/v1/llm/operator/strategy-signal-explain` → `/llm/analyst/strategy_signal_explain` | wie oben                                                                                  | wie oben                                                       | **Produktiv vorgesehen**; `verifiziert (Repo)`                                     |
| `POST /api/dashboard/llm/assist/{segment}`        | → `/v1/llm/assist/{segment}/turn` → `/llm/assist/turn`                                | wie oben                                                                                  | wie oben                                                       | **Implementiert**; Sichtbarkeit Health + Account; `verifiziert (Repo)`             |
| `GET /v1/signals/{id}/explain`                    | Gateway → DB (`fetch_signal_explain`)                                                 | Gateway JWT (Lesepfad Signals)                                                            | **Kein** LLM in diesem Request                                 | **Deterministischer Read**; `verifiziert (Repo)`                                   |
| Admin-Governance-Summary                          | Gateway → Orchestrator `/llm/governance/summary`                                      | Admin-Auth                                                                                | OpenAI/Fake                                                    | **Nicht** die zwei Dashboard-KI-Formulare; `verifiziert (Repo):` `routes_admin.py` |

**OpenAI-Key:** Liegt **nur** am **llm-orchestrator** (`OPENAI_API_KEY`). Weder Browser noch Dashboard-Container brauchen den Key für diese Strecken.

---

## 5. Was die KI heute wirklich ausgibt

### 5.1 Operator Explain

- **Strukturiertes JSON** (validiert gegen Schema): deutsche Erklärung, Referenzartefakte (Strings), nicht-autoritativer Hinweis.
- **Keine** Trades, keine Parameteränderung, keine Freigaben — `execution_authority` ist Konstante `none`.
- **Kein** automatisch mitlaufender „Gedankenstrom“; nur Antwort auf **eine** abgeschickte Frage pro Request.

### 5.2 Strategie-/Signalerklärung

- Felder u. a. `strategy_explanation_de`, `risk_and_caveats_de`, `referenced_input_keys_de`, `non_authoritative_note_de`.
- Optional **`chart_annotations`**: kann Linien/Marker/Bänder/Notizen beschreiben — die **UI rendert** das über `sanitizeLlmChartAnnotations` / `ProductCandleChart`, sofern Integration aktiv.
- **Fake-Provider:** liefert u. a. **eine** Test-Notiz in `chart_notes_de`, keine echten Preislinien — explizit mit `[TEST-PROVIDER]` markiert (`fake_provider.py`).

### 5.3 Assist-Turn

- Schema `assistant_turn.schema.json` (dynamische Anforderungen je Segment); Antwort u. a. `assistant_reply_de` im Fake-Modus mit klarer Test-Kennzeichnung.
- **Mehrere Turns** pro `conversation_id` möglich (Redis-Store mit TTL).

### 5.4 Signal-Detail „Explain“ aus DB (`fetchSignalExplain`)

- Markdown/Text-Felder, Risiko-JSONs — **Anzeige** auf der Signalseite; **kein** strukturiertes LLM-Envelope wie bei 5.2, sofern nicht explizit anders dokumentiert.

---

## 6. Was im Produkttext vielleicht größer klingt als im echten Ist-Zustand

- **„KI-Trading“ / „autonome KI“:** Widerspricht dem implementierten **Risk-/Signal-Kern ohne LLM** und `execution_authority: none` auf allen LLM-Outputs für diese Dashboard-Strecken.
- **„Vollständiger Operator-Chat“:** Operator Explain ist **single-turn pro Klick** ohne persistierten Verlauf; Multi-Turn ist **Assist** (eigenes Panel, andere UX).
- **„KI erklärt jedes Signal live“:** Die Seite zeigt **DB-Erklärungen** sofort; die **LLM**-Erklärung braucht **expliziten** Klick und funktionierenden Stack.
- **„Intelligentes Chart always-on“:** KI-Chart-Layer auf Signaldetail hängt an **LLM-Antwort** mit gültigen `chart_annotations` — nicht an jedem Chart der Konsole (dort typischerweise `llmChartIntegration={false}`).

`verifiziert (Repo):` Schemas, `PRODUCT_STATUS.md`, `ai-architecture.md`.

---

## 7. Was für sichtbare KI-Strategien im Chart noch fehlt

**Ist:** Auf **Signaldetail** ist der technische Pfad da: nach erfolgreicher Strategie-Signal-Erklärung können Annotationen auf die Kerzen gelegt werden.

**Lücken / nicht verifiziert als „fertig produkt“:**

- **Kein** durchgängiger KI-Overlay-Modus auf **Ops-, Health- oder Terminal-Chart** ohne separate Implementierung (Konsole nutzt `ConsoleLiveMarketChartSection` standardmäßig **ohne** LLM-Integration).
- **Qualität und Vollständigkeit** der vom **echten** Modell generierten `chart_annotations` ist **nicht** durch dieses Repo allein garantiert — nur Schema und Rendering-Pfad.
- **Strategie-Registry-Seite** zeigt **Tabellen/Metadaten**, **keinen** LLM-Chart.

---

## 8. Was für „Gedanken der KI“ bereits sichtbar ist oder nicht

| Art                                         | Sichtbar?                  | Wo / wie                                                                                            |
| ------------------------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------- |
| **LLM-Erklärungstext (Operator)**           | Ja, bei erfolgreichem Call | Health → Operator Explain                                                                           |
| **LLM-Strategie-/Risiko-Text (Signal)**     | Ja, bei erfolgreichem Call | Signaldetail → Panel                                                                                |
| **LLM-Chart-Annotationen**                  | Bedingt                    | Nur Signaldetail + erfolgreiche Antwort mit validen Annotationen + Layer an                         |
| **Assist-Antworten (Multi-Turn)**           | Ja                         | Health / Account → Assist-Tabs                                                                      |
| **Deterministische „Begründung“ im Signal** | Ja                         | Spalten, `reasons_json`, `decision_control_flow` in UI — **kein** laufendes LLM                     |
| **Persistente DB-Erklärung**                | Ja                         | `explain_short` / `explain_long_md` etc. vom Explain-Endpoint                                       |
| **Interne Prompts / Roh-Modelldenken**      | **Nein** (absichtlich)     | Nicht an Endnutzer-UI; Operator-Intel-Contract filtert u. a. `raw_llm` (`shared_py.operator_intel`) |

---

## 9. Wie man KI sauber auf 10/10 ausbauen könnte

**Zielbild (Soll-Vorschlag, nicht Implementierung):**

1. **Observability:** Metriken Latenz/Fehlerquote/Cached-Anteil pro Task-Typ am Gateway und Orchestrator; Dashboard nur Ops-Aggregat.
2. **Produkt-Klarheit:** Einheitliche Begriffe: „LLM-Erklärung“, „gespeicherte Erklärung“, „deterministischer Score“ — keine Vermischung in UI-Copy.
3. **Chart-KI:** Gezielt **Evaluations-Set** für `chart_annotations` (Fake + echte Modelle), Grenzen der Preis-Sanity in `sanitizeLlmChartAnnotations` dokumentieren.
4. **Assist vs. Explain:** Entweder zusammenführen (ein Konzept) oder klar segmentieren (Onboarding vs. Ops), damit Nutzer nicht zwei „Chats“ mit unklarem Scope haben.
5. **Governance:** Jede neue LLM-Route nur mit Gateway+BFF+Schema+Tests+`execution_authority`-Policy (wie in `PRODUCT_STATUS.md` angedeutet).
6. **Sicherheit / Kosten:** Quoten pro Tenant, Audit bereits vorhanden — ausbauen.

`[FUTURE]` — bewusst außerhalb aktueller Lieferung.

---

## 10. Übergabe an ChatGPT

**Checkliste für Antworten im Kontext dieses Repos:**

1. Unterscheide **LLM-Orchestrator-Pfade** vs. **DB-Reads** vs. **deterministische Engine**.
2. Nenne **OpenAI** nur für den **llm-orchestrator**; Fake nur für **local/test** und **verboten** in `APP_ENV` shadow/production laut `config.py`.
3. **Multi-Turn:** ja für **Assist**, nein für **Operator Explain** (stateless).
4. **Autonomes Trading durch diese LLM-Routen:** **Nein** — Schema und Produktregel.
5. Bei „leerer KI“: Keys, `LLM_ORCH_BASE_URL`/`HEALTH_URL_LLM_ORCHESTRATOR`, `INTERNAL_API_KEY`, JWT, Timeouts (bis ~125 s) prüfen.

---

## 11. Anhang: Dateipfade, Tests und Live-Nachweise

### 11.1 Zentrale Pfade

| Thema                                  | Pfad                                                                                                                                          |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Architekturüberblick                   | `ai-architecture.md`                                                                                                                          |
| Produktstatus KI                       | `PRODUCT_STATUS.md`                                                                                                                           |
| Orchestrator Service                   | `services/llm-orchestrator/src/llm_orchestrator/service.py`                                                                                   |
| Fake-Provider                          | `services/llm-orchestrator/src/llm_orchestrator/providers/fake_provider.py`                                                                   |
| OpenAI-Provider                        | `services/llm-orchestrator/src/llm_orchestrator/providers/openai_provider.py`                                                                 |
| Orchestrator-Config / Fake-Verbot Prod | `services/llm-orchestrator/src/llm_orchestrator/config.py`                                                                                    |
| Schemas                                | `shared/contracts/schemas/operator_explain.schema.json`, `strategy_signal_explain.schema.json`, `assistant_turn.schema.json`                  |
| Gateway Operator-LLM                   | `services/api-gateway/src/api_gateway/routes_llm_operator.py`                                                                                 |
| Gateway Assist                         | `services/api-gateway/src/api_gateway/routes_llm_assist.py`                                                                                   |
| Gateway Forward-Helfer                 | `services/api-gateway/src/api_gateway/llm_orchestrator_forward.py`                                                                            |
| BFF                                    | `apps/dashboard/src/app/api/dashboard/llm/operator-explain/route.ts`, `…/strategy-signal-explain/route.ts`, `…/llm/assist/[segment]/route.ts` |
| UI                                     | `OperatorExplainPanel.tsx`, `StrategySignalExplainPanel.tsx`, `AssistLayerPanel.tsx`, `SignalDetailMarketChartBlock.tsx`                      |
| Signal-Explain (DB)                    | `services/api-gateway/src/api_gateway/routes_signals_proxy.py` (`signal_explain`)                                                             |
| Verifikationsskript (Stack nötig)      | `scripts/verify_ai_operator_explain.py`                                                                                                       |
| Release-Gate verweist auf KI-Skript    | `scripts/release_gate.py`                                                                                                                     |

### 11.2 Automatisierte Tests

| Befehl                                                                                                                                                     | Ergebnis (diese Session, Host Windows)                              |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `python -m pytest tests/unit/api_gateway/test_routes_llm_operator.py -q`                                                                                   | **5 passed** in ~63 s — `verifiziert (Tests diese Session)`         |
| `cd apps/dashboard && pnpm test -- src/lib/__tests__/operator-explain-errors.test.ts src/lib/__tests__/strategy-signal-explain-errors.test.ts --runInBand` | **2 Suites, 15 tests passed** — `verifiziert (Tests diese Session)` |

Weitere sinnvolle Suites laut Doku: `tests/llm_orchestrator/test_structured_fake_provider.py`, `test_assist_turn.py` — `nicht verifiziert (Tests diese Session)`.

### 11.3 Live-Nachweis (manuell / Stack)

- `scripts/verify_ai_operator_explain.py` — `nicht verifiziert (Laufzeit)` in dieser Session (kein gestarteter Orchestrator hier dokumentiert).
- Manuelle Klicks: `ai-architecture.md` Abschnitt „Lokaler End-to-End-Test“.

### 11.4 OpenAI vs. Fake (kurz)

| Bedingung                                                | Verhalten                                                                                                                       |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `LLM_USE_FAKE_PROVIDER=true` am Orchestrator             | `FakeProvider.generate_structured` — deterministische, klar gekennzeichnete Antworten; Chart-Stub nur Struktur-Test             |
| `LLM_USE_FAKE_PROVIDER=false` + `OPENAI_API_KEY` gesetzt | OpenAI-Structured-Calls                                                                                                         |
| `LLM_USE_FAKE_PROVIDER=false` + fehlender Key            | Orchestrator-Fehlerpfad (Gateway oft 502 mit verständlicher Message) — `verifiziert (Repo):` `service.py`, `ai-architecture.md` |
| `APP_ENV` shadow/production                              | **Fake-Provider verboten** — Validierung in `config.py`                                                                         |

---

_Ende der Übergabedatei._
