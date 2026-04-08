# Candle Collector

## Ziel

Der Candle-Collector haelt fuer ein `example_only`-Symbol die Timeframes `1m`, `5m`, `15m`,
`1H` und `4H` aktuell. Er kombiniert initiale REST-Loads mit Live-Updates aus
dem Bitget Public Futures WebSocket und speichert die Kerzendaten in
`tsdb.candles`.

## WS Channels

Der Collector subscribt auf diese Public-WS-Channels:

- `candle1m`
- `candle5m`
- `candle15m`
- `candle1H`
- `candle4H`

Bitget pusht Candle-Updates bei laufenden Trades typischerweise etwa einmal pro
Sekunde. Ohne Trades kommen Updates entsprechend der Granularitaet.

## WS Payload

Der WS-Candle-Payload folgt dem Format:

```text
[startTime, open, high, low, close, baseVolume, quoteVolume, usdtVolume]
```

Der Collector parst Preise und Volumen als `Decimal`, nicht als `float`.
Die REST-Antwort kann je nach Endpoint effektiv nur `quoteVolume` statt eines
separaten `usdtVolume` liefern. In diesem Fall verwendet der Collector fuer
`usdt_vol` denselben Wert wie fuer `quote_vol`.

## REST Initial Load

Initiale Kerzen kommen von:

- `GET /api/v2/mix/market/candles`

Wichtige Parameter:

- `symbol=<example_symbol>`
- `productType=usdt-futures`
- `granularity=1m|5m|15m|1H|4H`
- `limit=<N>`
- optional `kLineType=MARKET`

Die API erlaubt bis zu `1000` Kerzen pro Request. Historische Verfuegbarkeit und
moegliche Rueckgabemengen koennen je Granularity variieren; deshalb bleibt das
Limit ueber ENV steuerbar.

## Storage

Migration:

```bash
python infra/migrate.py
```

Schema:

- `tsdb.candles`
- PK: `(symbol, timeframe, start_ts_ms)`
- Preis- und Volumenfelder als `numeric`

## Candle Close

Wenn fuer ein Timeframe eine neue `start_ts_ms` groesser als die aktuelle offene
Kerze auftaucht, betrachtet der Collector die vorherige Kerze als geschlossen
und emittiert ein Event in:

- `events:candle_close`

Das Event wird als `EventEnvelope` publiziert und nutzt als `dedupe_key` die
Kombination aus `symbol`, `timeframe` und `start_ts_ms`, damit Reconnects keine
doppelten Candle-Close-Events verursachen.

## Alignment und Retention

- Jede Kerze wird auf `start_ts_ms % timeframe_ms == 0` geprueft
- Unsaubere Alignments werden geloggt
- Alte Kerzen werden bei Start und danach alle 12 Stunden anhand der
  `TSDB_RETENTION_DAYS_CANDLES_*`-Werte geloescht

## Security

- Public Market Data benoetigt keine API-Keys
- `.env.example` bleibt committed
- `.env.local` bleibt lokal und darf niemals committed werden
