# Market Stream

## Ziel

Der Dienst `market-stream` verbindet den Bitget Public Futures WebSocket, haelt
eine stabile Subscription aktiv, normalisiert eingehende Frames und schreibt sie
primaer als EventEnvelope in feste Redis Streams wie `events:market_tick`,
`events:candle_close` und `events:funding_update`. Optional kann ein Raw-Event
weiterhin als Debug-Mirror in `stream:market:raw` und in Postgres `raw_events`
landen. Zusaetzlich pflegt der Dienst Candles, Trades, Ticker/Funding/OI sowie
einen lokalen L2-Orderbook-State mit Slippage-Metriken.

## Betriebsregeln

- Bitget verlangt ein Ping mindestens alle 30 Sekunden.
- Bleibt ein Pong aus, muss die Verbindung neu aufgebaut werden.
- Outbound-Limit: maximal 10 Nachrichten pro Sekunde, inklusive Ping und
  Subscribe/Unsubscribe.
- Fuer Stabilitaet sollte eine Verbindung unter 50 aktiven Channels bleiben.
- Bitget weist auf moeglichen WS Message-Loss hin. REST-Fallback ist deshalb
  empfohlen.
- In der Praxis koennen laufende Market-Data-Frames das einzige Heartbeat-Signal
  sein. Der Dienst sendet deshalb weiterhin aktiv `ping`, wertet aber auch
  eingehenden Traffic als Liveness-Signal aus, um keine falschen Reconnects
  waehrend eines gesunden Streams auszulosen.

## Demo und Live

- Die effektive WS-Domain kommt aus `shared_py.bitget.BitgetSettings`.
- Im Demo-Modus wird automatisch die offizielle `wspap.bitget.com`-Domain
  genutzt.
- Es werden in Prompt 5 nur Public-WS-Channels verwendet.

## Lokales Setup

- `.env.example` bleibt committed.
- `.env.local` bleibt lokal und darf niemals committed werden.
- Standardport des Health-HTTP-Dienstes: `8010`.

Wichtige ENV-Werte:

- `MARKET_STREAM_PORT=8010`
- `MARKET_STREAM_WS_MODE=classic`
- `MARKET_STREAM_ENABLE_RAW_PERSIST=false`
- `BITGET_CANDLE_INITIAL_LOAD_LIMIT=300`
- `BITGET_CANDLE_KLINE_TYPE=MARKET`
- `ORDERBOOK_MAX_LEVELS=50`
- `ORDERBOOK_CHECKSUM_LEVELS=25`
- `ORDERBOOK_RESYNC_ON_MISMATCH=true`
- `SLIPPAGE_SIZES_USDT=1000,5000,10000`
- `OI_SNAPSHOT_INTERVAL_SEC=30`
- `FUNDING_SNAPSHOT_INTERVAL_SEC=60`
- `SYMBOL_PRICE_SNAPSHOT_INTERVAL_SEC=5`
- `REDIS_URL=redis://localhost:6379`
- `EVENTBUS_DEFAULT_BLOCK_MS=2000`
- `EVENTBUS_DEFAULT_COUNT=50`
- `EVENTBUS_DEDUPE_TTL_SEC=86400`
- `DATABASE_URL=postgresql://postgres:changeme@localhost:5432/bitget_ai`

## Migration

```bash
python infra/migrate.py
```

## Start

```bash
cd services/market-stream
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
python -m market_stream.main
```

## Verify

```bash
curl -s http://localhost:8010/health
curl -s http://localhost:8010/stats
redis-cli XINFO STREAM events:market_tick
redis-cli XREAD COUNT 1 STREAMS events:market_tick 0
redis-cli XINFO STREAM events:candle_close
redis-cli XREAD COUNT 3 STREAMS events:candle_close 0
redis-cli XINFO STREAM events:funding_update
redis-cli XREAD COUNT 3 STREAMS events:funding_update 0
redis-cli XINFO STREAM stream:market:slippage_metrics
redis-cli XREAD COUNT 1 STREAMS stream:market:slippage_metrics 0
psql "$DATABASE_URL" -c "select count(*) from tsdb.trades where symbol='<example_symbol>';"
psql "$DATABASE_URL" -c "select count(*) from tsdb.ticker where symbol='<example_symbol>';"
psql "$DATABASE_URL" -c "select count(*) from tsdb.orderbook_top25 where symbol='<example_symbol>';"
```

Erwartete Logs:

- `WS connected`
- `subscribed ticker <example_symbol>`
- `subscribed trade <example_symbol>`
- `subscribed books <example_symbol>`
- `subscribed books5 <example_symbol>`
- `subscribed candle1m <example_symbol>`
- `subscribed candle5m <example_symbol>`
- `subscribed candle15m <example_symbol>`
- `subscribed candle1H <example_symbol>`
- `subscribed candle4H <example_symbol>`
- `initial load REST call endpoint=/api/v2/mix/market/candles`
- `starting ticker REST snapshot refresh`
- `WS ping sent`
- `WS pong received`
- `Events published`
- `published events:candle_close`
- `published events:market_tick`
- `published events:funding_update`

## REST Gap-Fill

Gap-Fill wird ausgelost bei:

- erfolgreichem Reconnect
- erkannter Sequence-Luecke
- stale data ohne neue Events fuer eine definierte Zeit

Verwendete Endpunkte:

- Candles: `/api/v2/mix/market/candles`
- Trades: `/api/v2/mix/market/fills-history`
- Ticker (REST-Spiegel): `/api/v2/mix/market/ticker`
- Merge-Depth (Orderbuch-Snapshot fuer Replay): `/api/v2/mix/market/merge-depth`

Fuer `fills-history` wird das Zeitfenster auf maximal 7 Tage begrenzt.

## Sequenzen, Checksumme, Resync

- Globale WS-`seq` wird **pro Kanal und instId** gefuehrt (nicht mehr ueber alle Kanaele gemischt).
- `books` / `books5` nutzen das **eigene Orderbuch-Protokoll** (Seq/Checksum im `OrderbookCollector`), nicht den generischen Seq-Gap-Pfad.
- Bei Checksummenfehler oder Seq-Desync: Resubscribe `books5` dann `books` (konfigurierbar `ORDERBOOK_RESYNC_ON_MISMATCH`).

## Stale-Daten, Reconnect, Eskalation

- `MARKET_STREAM_WS_STALE_AFTER_SEC`: keine neuen WS-Events (ingest_ts) -> REST-Gapfill (Kerzen, Trades, optional Ticker + Merge-Depth).
- `MARKET_STREAM_STALE_ESCALATION_MAX_CYCLES`: wiederholte Stale-Erkennung (ca. alle 5 s) ohne neue Frames -> **bewusster WS-Reconnect** (Exception im Client-Loop).
- Nach erfolgreichem Gapfill: **REST-Ticker-Snapshots** (OI/Funding/Preis) und bei Reconnect/Seq-Gap/**stale-data** zusaetzlich **Orderbuch-Resync**.

## Downstream: Feed-Gesundheit und Ready-Gate

- Redis-Stream **`events:market_feed_health`**: periodisch (`MARKET_STREAM_FEED_HEALTH_INTERVAL_SEC`) mit `ok`, Alter von Ticker/Orderbuch/Trades, WS-Zustand, `orderbook_desynced`, Gapfill-Metadaten. Consumer koennen eigene Gates bauen.
- **`GET /ready`** enthaelt Check **`data_freshness`**: Ticker- und Orderbuch-Timestamps duerfen `MARKET_STREAM_READY_MAX_DATA_AGE_SEC` nicht ueberschreiten (nach **`MARKET_STREAM_READY_BOOT_GRACE_SEC`**). Optional `MARKET_STREAM_READY_REQUIRE_FRESH_TRADES=true` fuer illiquide Symbole bewusst aktivieren.

## Last, Retention, Sampling (Kurz)

| Pfad                               | Typische Last             | Retention / Sampling                                                                       |
| ---------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------ |
| WS -> Redis `events:market_tick`   | hoch (ticker/trades)      | Stream-Laenge betrieblicher Policy / Trimming                                              |
| WS -> TSDB trades/ticker/orderbook | mittel                    | siehe `TSDB_RETENTION_DAYS_*` Kerzen; Trades/Ticker/OB in Migration `010_tsdb_market_core` |
| REST periodisch (OI/Funding/Preis) | niedrig (Intervalle ENV)  | gleiche TSDB-Ticker-Tabelle                                                                |
| `events:market_feed_health`        | niedrig (z. B. alle 10 s) | kurze History reicht fuer Alerts                                                           |
| `MARKET_STREAM_ENABLE_RAW_PERSIST` | optional hoch             | Postgres `raw_events` nur bei Bedarf                                                       |

## Fehlerbilder (Betrieb)

| Symptom                                    | Moegliche Ursache                      | Erwartetes Verhalten                                           |
| ------------------------------------------ | -------------------------------------- | -------------------------------------------------------------- |
| `/ready` -> `data_freshness` false         | WS haengt, Symbol inaktiv, Rate-Limits | Gapfill, spaeter Reconnect-Eskalation; Health-Event `ok=false` |
| `orderbook_desynced`                       | Message-Loss, Checksumme               | Resync-Subscribe; Ready bleibt false bis konsistent            |
| REST gap-fill warning (ticker/merge-depth) | Endpoint/Parameter, Demo vs Live       | Kerzen/Trades trotzdem; Log pruefen                            |
| Hauefige Reconnects                        | Netz, Bitget-Wartung                   | `reconnect_count` in `/stats`; Backoff im WS-Client            |
