# structure-engine

Marktstruktur-Service: konsumiert `events:candle_close`, schreibt Swings und
Zustand nach Postgres, publiziert `events:structure_updated`.

## Lauf

```bash
cd services/structure-engine
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -e .
set DATABASE_URL=...
set REDIS_URL=...
python -m structure_engine.main
```

## Endpoints

- `GET /health`
- `GET /structure/latest?symbol=<example_symbol>&timeframe=1m`

Siehe `docs/structure.md` für Regeln (Pivot, BOS/CHOCH, Kompression, Boxen).
