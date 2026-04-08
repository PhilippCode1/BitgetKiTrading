# Live-Terminal (Prompt 25)

Browser: **`/terminal`** (Root `/` leitet dorthin um). Daten kommen über **api-gateway** — keine direkten Calls zu Microservices.

## API (api-gateway)

### `GET /v1/live/state`

| Query       | Default                      | Max                                     |
| ----------- | ---------------------------- | --------------------------------------- |
| `symbol`    | `<example_symbol>`           | —                                       |
| `timeframe` | 1m                           | wird nach DB normalisiert (`1h` → `1H`) |
| `limit`     | `LIVE_STATE_DEFAULT_CANDLES` | `LIVE_STATE_MAX_CANDLES`                |

**Response (Auszug):**

- `candles[]`: `time_s` = Unix-**Sekunden** (Bar-Start, kompatibel zu [Lightweight Charts](https://tradingview.github.io/lightweight-charts/) `time` als UTCTimestamp).
- `latest_signal`: Join `app.signals_v1` + `app.signal_explanations` (Begründung, `risk_warnings_json`).
- `latest_drawings`: aktive `app.drawings` mit UI-Feldern `price_lines` / `trendline` aus `geometry_json`.
- `latest_news`: relevante `app.news_items`.
- `paper_state`: offene `paper.positions`, Mark-Preis aus `tsdb.ticker`, letzte geschlossene Position.
- `health`: `db`, `redis`.
- `online_drift`: Zeile `learn.online_drift_state` (Scope `global`), falls vorhanden.
- `data_lineage`: Liste von Teilstrecken (`segment_id`, `has_data`, `producer_de`, `why_empty_de`, `next_step_de`) — erklärt fehlende Daten ohne stille Lücken.
- Leser-Envelope (optional): `status`, `message`, `empty_state`, `degradation_reason`, `next_step`.

### `GET /v1/live/stream` (SSE)

- `text/event-stream`, Events: `ping`, `candle`, `signal`, `drawing`, `news`, `paper`.
- Quelle: **Redis Streams** (`XREAD`, Cursor `$`), keine DB-Polling-Schleife im Stream.
- Abonnierte Streams: u. a. `events:candle_close`, `events:signal_created`, `events:trade_opened`, `events:trade_updated`, `events:trade_closed`, … (kanonisch: `shared/contracts/catalog/event_streams.json`).
- **Coalescing**: max. 10 Events/s (Schutz vor UI-Überlastung).
- **Ping**: alle `LIVE_SSE_PING_SEC` Sekunden.
- `LIVE_SSE_ENABLED=false` → HTTP 503 (Dashboard nutzt Polling-Fallback).

## Frontend

- **Charts**: [lightweight-charts](https://tradingview.github.io/lightweight-charts/) — `createChart`, `addCandlestickSeries`, `setData` / `update`.
- **PriceLines**: [`createPriceLine`](https://tradingview.github.io/lightweight-charts/docs/api/interfaces/ISeriesApi#createpriceline) auf der Candlestick-Serie; Entfernen via `removePriceLine`.
- **Marker**: [`setMarkers`](https://tradingview.github.io/lightweight-charts/docs/api/interfaces/ISeriesApi#setmarkers) für News-Zeitpunkte.
- **Trendlinien**: zusätzliche `LineSeries` mit zwei Punkten `(time, value)` aus `trendline` (ms → s).

Steuerung: Timeframe-Toggles, Overlays (Zeichnungen / News), **Freeze** (SSE schließen, optional Polling stoppt bei Freeze).

## ENV

| Variable                            | Dienst    | Hinweis                       |
| ----------------------------------- | --------- | ----------------------------- |
| `NEXT_PUBLIC_API_BASE_URL`          | Dashboard | öffentlich, **keine Secrets** |
| `NEXT_PUBLIC_DEFAULT_SYMBOL`        | Dashboard |                               |
| `NEXT_PUBLIC_DEFAULT_TF`            | Dashboard |                               |
| `NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS` | Dashboard | Fallback                      |
| `LIVE_STATE_MAX_CANDLES`            | Gateway   |                               |
| `LIVE_STATE_DEFAULT_CANDLES`        | Gateway   |                               |
| `LIVE_SSE_ENABLED`                  | Gateway   |                               |
| `LIVE_SSE_PING_SEC`                 | Gateway   |                               |
| `CORS_ALLOW_ORIGINS`                | Gateway   | komma-separiert               |

## DB

- Migration **`200_ui_prefs.sql`**: `app.ui_preferences` (persistente UI-Defaults, ohne Secrets).

## Tests

```bash
bash tests/dashboard/test_live_state_contract.sh
```

## Sicherheit

- SSE liefert nur **UI-taugliche** Payloads (keine API-Keys).
- Prod: Auth/ACL später (Prompt 26); Rate-Limits am Gateway.
