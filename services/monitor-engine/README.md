# monitor-engine

Periodische Ueberwachung: HTTP `/health`/`/ready`/`/metrics` anderer Services, Redis-Streams (`XPENDING`, `XINFO GROUPS`, `XINFO STREAM`), Datenfrische in Postgres, DLQ/LLM-Heuristik. Schreibt nach `ops.*` und publiziert `events:system_alert` (Dedupe + Rate-Limit). **Alert-`details`** enthalten strukturierte Betreiberhinweise (`operator_*`, `correlation`) via `alerts/operator_context.py` — siehe `docs/cursor_execution/20_monitor_alerts_and_observability.md`.

## Endpoints

| Pfad                               | Beschreibung                                                                                                                                                                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /health`                      | Liveness                                                                                                                                                                                                                      |
| `GET /ready`                       | Postgres + Redis                                                                                                                                                                                                              |
| `GET /metrics`                     | Prometheus: HTTP-Middleware + Stream-Lag, Datenfrische, Online-Drift, Shadow/Live, **Live-Reconcile/Kill-Switch**, **Trading-SQL-Gauges** (Order-Fail-Rate, Slippage, Signal-Reject-Ratio, …) — siehe `docs/observability.md` |
| `GET /ops/alerts/open`             | Offene Alerts                                                                                                                                                                                                                 |
| `POST /ops/alerts/{alert_key}/ack` | Alert quittieren (`alert_key` kann Slashes enthalten)                                                                                                                                                                         |
| `POST /ops/run-now`                | Einen Check-Zyklus sofort ausfuehren                                                                                                                                                                                          |

## ENV

Siehe Root `.env.example` (Abschnitt **Monitor Engine**). Mindestens:

- `DATABASE_URL`, `REDIS_URL`
- `MONITOR_SERVICE_URLS`, `MONITOR_STREAMS`, `MONITOR_STREAM_GROUPS`
- Schwellen `THRESH_*`

## Start (lokal)

```bash
cd services/monitor-engine
pip install -e .
set DATABASE_URL=postgresql://...
set REDIS_URL=redis://...
set MONITOR_ENGINE_PORT=8110
python -m monitor_engine.main
```

`PYTHONPATH` muss `shared/python/src` enthalten (wie in Docker).

## Tests

```bash
pytest tests/monitor_engine -q
```

## Docker

`docker compose up -d monitor-engine` (siehe Root `docker-compose.yml`).

Prometheus + Grafana (optional):

```bash
docker compose --profile observability up -d prometheus grafana
```
