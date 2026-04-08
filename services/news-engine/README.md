# news-engine

Ingestion für **`app.news_items`** aus CryptoPanic, NewsAPI, CoinDesk RSS und GDELT DOC 2.0.
Veröffentlicht **`events:news_item_created`**.

Regelbasiertes **Scoring** (optional LLM via Orchestrator) schreibt Scores in die DB und
publiziert **`events:news_scored`** (siehe `docs/news_scoring.md`).

## Abhängigkeiten

- `shared_py` (Eventbus): Repo-Root `shared/python/src` auf `PYTHONPATH` legen, z. B.

```bash
set PYTHONPATH=..\..\shared\python\src
```

(Linux/macOS: `export PYTHONPATH=../../shared/python/src`)

## Install & Start

```bash
cd services/news-engine
python -m venv .venv
pip install -e .
set DATABASE_URL=postgresql://...
set REDIS_URL=redis://...
set NEWS_FIXTURE_MODE=true
python -m news_engine.main
```

Port: `NEWS_ENGINE_PORT` (Default `8060`).

## Endpoints

- `GET /health`
- `POST /ingest/now`
- `POST /score/now`
- `GET /news/latest?limit=20`
- `GET /news/scored?min_score=0&limit=20`
- `GET /news/{id}` (DB-`id`)

## Tests (ohne Keys)

```bash
pytest -q tests/news_engine
```

Siehe `docs/news_engine.md`.
