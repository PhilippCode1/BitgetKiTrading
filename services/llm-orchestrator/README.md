# llm-orchestrator

Zentraler LLM-Dienst: **OpenAI**, **Fake** (Tests), Structured Output mit
**jsonschema**-Validation, **Redis-Cache**, **Retry/Backoff**, **Circuit Breaker**;
Event **`events:llm_failed`**.

## PYTHONPATH

`shared/python/src` für `shared_py` zum Repo-Root hinzufügen (wie bei anderen Services).

## Start (Fake-Mode)

```bash
cd services/llm-orchestrator
pip install -e .
set REDIS_URL=redis://localhost:6379/0
set LLM_USE_FAKE_PROVIDER=true
set LLM_ORCH_PORT=8070
python -m llm_orchestrator.main
```

## Beispiel

```bash
curl -s http://localhost:8070/health
curl -s -X POST http://localhost:8070/llm/structured ^
  -H "Content-Type: application/json" ^
  -H "X-Internal-Service-Key: %INTERNAL_API_KEY%" ^
  -d "{\"schema_json\":{\"type\":\"object\",\"properties\":{\"a\":{\"type\":\"string\"}},\"required\":[\"a\"]},\"prompt\":\"test\"}"
```

`python -m llm_orchestrator.main` startet uvicorn mit **Factory** (`create_app`) — kein App-Objekt beim Modulimport, damit Tests ohne vollstaendige `.env.local` `create_app()` erst nach gesetzten ENV aufrufen koennen.

## Tests

```bash
pytest -q tests/llm_orchestrator
```

Dokumentation: `docs/llm_orchestrator.md`. Contracts: `shared/contracts/schemas/*.schema.json`,
kuratiertes Wissen: `docs/llm_knowledge/`. Analyst-Endpoints unter `/llm/analyst/*`; bei
`SERVICE_INTERNAL_API_KEY` Header `X-Internal-Service-Key` setzen.

## API-Vertrag & Determinismus

- **`GET /health`** liefert `api_contract_version` (aktuell `llm-orch-api-v1`) und einen kurzen Hinweis zu **Backoff ohne RNG** (`retry/backoff.py`; Standard `LLM_BACKOFF_JITTER_RATIO=0`).
- **Kein Tool-Calling** im `LLMProvider`-Protokoll — nur `generate_structured`.
- Modellausgaben bleiben stochastisch; Retries/Circuit sind operational deterministisch bis auf Provider-Latenz und Cache-Zustand.
