# Feature-, Structure- und Drawing-Pipeline (Diagnose & Live-State)

**Zweck:** Nachvollziehbarer Datenpfad von **Kerzen-Events** über **Features**, **Struktur** und **Drawings** bis zu den **Signalen** — mit klaren Health-Feldern, `data_lineage`-Texten und SQL-/HTTP-Nachweisen.

**Referenz:** `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md`, `02_SYSTEM_TOPOLOGIE_UND_SERVICES.md`.

---

## 1. Datenfluss (vereinfacht)

| Stufe | Dienst           | Redis-Ingress              | Postgres-Schreiben                                          | Redis-Egress               |
| ----- | ---------------- | -------------------------- | ----------------------------------------------------------- | -------------------------- |
| 1     | market-stream    | —                          | `tsdb.candles`, Ticker, Orderbuch                           | `events:candle_close`      |
| 2     | feature-engine   | `events:candle_close`      | `features.candle_features`                                  | —                          |
| 3     | structure-engine | `events:candle_close`      | `app.structure_state`, `app.swings`, `app.structure_events` | `events:structure_updated` |
| 4     | drawing-engine   | `events:structure_updated` | `app.drawings`                                              | `events:drawing_updated`   |
| 5     | signal-engine    | mehrere Streams            | `app.signals_v1`                                            | `events:signal_created`    |

**Compose-Reihenfolge (Auszug):** feature + structure nach market-stream; drawing nach structure; signal nach feature + structure + drawing + news (`docker-compose.yml`).

---

## 2. Diagnose pro Stufe

### 2.1 feature-engine (`:8020`)

- **`GET /health`:** `pipeline_expectations`, Worker-Stats (`redis_connected`, `group_ready`, `processed_events`, `dlq_events`, `last_error`, …).
- **Typische Ursachen leerer `features.candle_features`:** Redis down, keine `candle_close`-Events, DLQ wegen Qualitaetsgattern, fehlende Kerzen in `tsdb.candles`, Instrument-Metadaten.

### 2.2 structure-engine (`:8030`)

- **`GET /health`:** `pipeline_expectations`, **`last_structure_skip`**: z. B. `insufficient_candles`, `unsupported_timeframe`, `skip_non_candle_close`, oder `null` nach erfolgreichem Lauf.
- **Typische Ursachen leerer `app.structure_state`:** zu wenig Bars fuer Pivot-Lookback, falsches TF, Redis, DB-Fehler.

### 2.3 drawing-engine (`:8040`)

- **`GET /health`:** `pipeline_expectations`, **`last_drawing_skip`**: z. B. `no_close_candle`, `no_geometry_candidates`, `no_drawing_revision`, `unsupported_timeframe`, oder `null` bei neuer Revision.
- **Typische Ursachen leerer `app.drawings`:** kein `structure_state`, veraltetes Orderbuch (`tsdb.orderbook_top25`), keine Kandidaten-Geometrie.

### 2.4 api-gateway Live-State

- **`GET /v1/live/state`:** zusaetzlich **`structure_state`** (Kurzsummary aus `app.structure_state` oder `null`).
- **`data_lineage`:** neues Segment **`structure`**; Segmente **`features`**, **`drawings`**, **`signals`** mit **bedingten** `why_empty_*`-Texten (DB vs. Redis vs. fehlende Upstream-Daten vs. Producer).
- Optional **`diagnostic_tags`** pro Segment bei leeren Daten (z. B. `redis_unavailable`, `upstream:missing_candles`, `producer:structure_engine`).

---

## 3. Nachweise

### 3.1 Unit-Tests (Gateway)

```text
python -m pytest tests/unit/api_gateway/test_db_live_queries.py -q
```

### 3.2 Health der drei Engines (laufender Stack)

```text
curl -sS http://127.0.0.1:8020/health
curl -sS http://127.0.0.1:8030/health
curl -sS http://127.0.0.1:8040/health
```

Erwartung: JSON mit `pipeline_expectations` und Worker-Metriken; bei Verarbeitung `last_structure_skip` / `last_drawing_skip` meist `null`.

### 3.3 Minimaler End-to-End-Check (SQL)

Mit psql / Admin-Tool, Symbol und TF anpassen:

```sql
-- Kerzen
SELECT COUNT(*) FROM tsdb.candles WHERE symbol = 'BTCUSDT' AND timeframe = '1m';

-- Features
SELECT start_ts_ms, computed_ts_ms FROM features.candle_features
WHERE symbol = 'BTCUSDT' AND timeframe = '1m' ORDER BY start_ts_ms DESC LIMIT 3;

-- Struktur
SELECT last_ts_ms, trend_dir, updated_ts_ms FROM app.structure_state
WHERE symbol = 'BTCUSDT' AND timeframe = '1m';

-- Drawings
SELECT drawing_id, type, status, updated_ts FROM app.drawings
WHERE symbol = 'BTCUSDT' AND timeframe = '1m' AND status = 'active' ORDER BY updated_ts DESC LIMIT 5;
```

### 3.4 Live-State JSON (Gateway)

```text
curl -sS -H "Authorization: Bearer <JWT>" "http://127.0.0.1:8000/v1/live/state?symbol=BTCUSDT&timeframe=1m&limit=50"
```

Pruefen: `structure_state`, `latest_feature`, `latest_drawings`, `data_lineage` (Segmente `features`, `structure`, `drawings`, `signals`).

---

## 4. Redis-Streams (Operator)

Kanonische Namen aus `shared/contracts/catalog/event_streams.json`:

- Ingress feature + structure: **`events:candle_close`**
- Structure → Drawing: **`events:structure_updated`**
- Drawing SSE: **`events:drawing_updated`**

Gruppen (Defaults): `feature-engine`, `structure-engine`, `drawing-engine` — siehe jeweilige `GET /ready`-Checks und Service-ENV.

---

## 5. Bekannte offene Punkte

- **[FUTURE]** Gateway koennte optional **XPENDING**-Metriken spiegeln (echter Redis-Lag) — aktuell nur textuelle Hinweise in `data_lineage`.
- **[TECHNICAL_DEBT]** `last_drawing_skip=no_drawing_revision` bedeutet „keine Aenderung gegenueber Fingerprint“ — kein Fehlerzustand.
