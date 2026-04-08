# drawing-engine

Konsumiert `events:structure_updated`, erzeugt versionierte Drawings in Postgres,
validiert gegen `shared/contracts/schemas/drawing.schema.json`, publiziert
`events:drawing_updated`.

## Start

```bash
cd services/drawing-engine
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
set DATABASE_URL=...
set REDIS_URL=...
python -m drawing_engine.main
```

## API

- `GET /health`
- `GET /drawings/latest?symbol=<example_symbol>&timeframe=1m`
- `GET /drawings/history?parent_id=<uuid>`

Siehe `docs/drawings.md`.
