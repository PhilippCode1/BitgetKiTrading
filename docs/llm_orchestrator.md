# LLM-Orchestrator (Analystenlayer)

Dienst `services/llm-orchestrator`: **strukturierte** LLM-Ausgaben fuer News, Kontext,
Hypothesen, Post-Trade, Operator-Erklaerungen und Journal-Zusammenfassungen.

**Nicht** im Verantwortungsbereich: Handelsentscheidung, Risk-Gates, Broker, Order-Submit,
Strategieparameter, Routing-Policies, Modellregistry — das bleibt deterministischer Kern /
Spezialisten-Stack.

## Architekturprinzipien

| Aspekt     | Umsetzung                                                                                                            |
| ---------- | -------------------------------------------------------------------------------------------------------------------- |
| Ausgabe    | JSON gemaess Draft 2020-12 Schema, Pflichtvalidierung mit `jsonschema`                                               |
| Cache      | Redis-Key aus `provider`, `model`, `schema_hash`, `input_hash` (Prompt+Temperatur kanonisch)                         |
| Resilienz  | Retries, Backoff (ohne RNG: `jitter_ratio=0` Default; sonst fester Anteil), **Circuit Breaker**, Provider **OpenAI** |
| Retrieval  | Nur **kuratierte** Snippets unter `docs/llm_knowledge/` laut `manifest.json` (kein offenes Web-RAG)                  |
| Audit      | Jede erfolgreiche Antwort enthaelt `provenance` (siehe unten)                                                        |
| Sicherheit | Kein Tool-Calling; keine direkte Orderhoheit; interner Service-Auth optional/zwang in Prod                           |

## Provenance (API)

Erfolgreiche Calls liefern zusaetzlich zu `ok`, `cached`, `provider`, `model`, `result`:

- `provenance.task_type` — z. B. `news_summary`, `analyst_hypotheses`, `structured_adhoc`
- `provenance.llm_derived` — immer `true` fuer diesen Dienst
- `provenance.quantitative_core_note_de` — Hinweis, dass Signal/Risk/Broker ausserhalb liegen
- `provenance.schema_id` — JSON-Schema `$id` falls gesetzt
- `provenance.prompt_fingerprint_sha256` — SHA-256 ueber den **finalen** Prompt (inkl. Retrieval-Text)
- `provenance.retrieval` — `null` oder `{ "source": "docs/llm_knowledge", "chunks": [{ "id", "content_sha256" }] }`

**Interpretation:** Alle Felder unter `result` sind modellbasiert und schema-validiert; harte quantitative
Logik (Scores, Gates, Stops) kommt aus anderen Services und muss dort auditiert werden.

## Kuratiertes Wissen (`docs/llm_knowledge`)

- `manifest.json` listet Chunks mit `id`, relativem `path`, `tags`, `keywords`.
- `KnowledgeRetriever` filtert nach **Task-Tags** (kein beliebiges Einlesen von `docs/`).
- Pfade werden gegen Path-Traversal geprueft; nur Dateien unter dem Knowledge-Root.
- Docker-Image kopiert `shared/contracts` und `docs/llm_knowledge` (siehe `services/llm-orchestrator/Dockerfile`).

Steuerung: `LLM_KNOWLEDGE_MAX_CHUNKS` (0 = Retrieval aus), `LLM_KNOWLEDGE_EXCERPT_CHARS`.

## API

| Methode | Pfad                                    | Zweck                                                                                 |
| ------- | --------------------------------------- | ------------------------------------------------------------------------------------- |
| GET     | `/health`                               | Redis, Circuit, Fake-Flag, **`api_contract_version`**, Kurztext Backoff-Determinismus |
| POST    | `/llm/structured`                       | Freies Schema + Prompt; optional `task_type` (Audit, ohne Retrieval)                  |
| POST    | `/llm/news_summary`                     | News → `news_summary.schema.json` + Retrieval                                         |
| POST    | `/llm/analyst/hypotheses`               | Kontext-JSON → Hypothesen-Schema                                                      |
| POST    | `/llm/analyst/context_classification`   | Narrativ + optional Instrument-Hint → Kontext-Buckets                                 |
| POST    | `/llm/analyst/post_trade_review`        | Trade-Fakten → Review-Schema                                                          |
| POST    | `/llm/analyst/operator_explain`         | Frage + Readonly-Kontext → Erklaerung (`execution_authority=none` im Schema)          |
| POST    | `/llm/analyst/strategy_journal_summary` | Journal-Ereignisse → Summary-Schema                                                   |

Alle POST-Endpunkte (ausser oeffentliche Health/Ready) erfordern bei konfiguriertem
`SERVICE_INTERNAL_API_KEY` den Header `X-Internal-Service-Key`.

**API-Contract-Version:** Feld `api_contract_version` in `/health` entspricht
`llm_orchestrator.constants.LLM_ORCHESTRATOR_API_CONTRACT_VERSION`. Bei entfernten
Pfaden, geaenderten Pflichtfeldern oder neuem Provenance-Schema: Version erhoehen und
Release-Notes ergaenzen.

## JSON-Schemas (Contracts)

Repo-Pfad: `shared/contracts/schemas/`

- `news_summary.schema.json`
- `analyst_hypotheses.schema.json`
- `analyst_context_classification.schema.json`
- `post_trade_review.schema.json`
- `operator_explain.schema.json`
- `strategy_journal_summary.schema.json`

## ENV (Auszug)

`.env.example`: `LLM_ORCH_PORT`, `REDIS_URL`, `LLM_CACHE_TTL_SEC`, `LLM_MAX_RETRIES`,
`LLM_TIMEOUT_MS`, `LLM_MAX_PROMPT_CHARS`, `LLM_BACKOFF_*`, `LLM_CIRCUIT_*`,
`LLM_KNOWLEDGE_MAX_CHUNKS`, `LLM_KNOWLEDGE_EXCERPT_CHARS`, `LLM_USE_FAKE_PROVIDER`,
`OPENAI_*` (nur OpenAI; kein Gemini).

## Sicherheit

- Keine vollstaendigen Prompts in Standard-Logs (Fingerprint/Hashes, Laengen).
- Cache-Keys enthalten keine API-Keys.
- Fake-Provider in **shadow/production** gesperrt (`LLMOrchestratorSettings`).

## News-Engine

Optionaler Aufruf `POST /llm/news_summary` vom News-Engine — bleibt Anreicherung;
authoritatives deterministisches Scoring liegt im News-Engine-Pfad.
