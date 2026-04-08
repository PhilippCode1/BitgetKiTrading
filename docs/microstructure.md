# Microstructure Ingestion

## Ziel

Prompt 7 erweitert `market-stream` um Microstructure-Daten fuer ein `example_only`-Symbol:

- L2 Local Orderbook mit `books` plus `books5` Recovery
- Trades aus dem Public-WS-Channel `trade`
- Ticker/Funding/OI aus `ticker` plus REST-Snapshots
- Slippage-Metriken im Redis Stream `stream:market:slippage_metrics`

## Depth Channels

Bitget Public Futures nutzt fuer Depth:

- `books`: initialer Snapshot, danach inkrementelle Updates
- `books5`: jedes Mal ein Snapshot, geeignet als Recovery-Fallback

Typische Push-Frequenzen laut Bitget:

- `books`, `books5`, `books15`: etwa `150ms`
- `books1`: etwa `10ms`

Der lokale Orderbook-State fuehrt Bids absteigend und Asks aufsteigend. Updates
werden nach Bitget-Merge-Regel verarbeitet:

- `amount == 0` loescht das Level
- vorhandene Levels werden ersetzt
- neue Levels werden eingefuegt

## Checksum / CRC32

Die Verifikation nutzt die obersten `25` Levels pro Seite und baut den String
abwechselnd:

```text
bid1:amt1:ask1:amt1:bid2:amt2:ask2:amt2:...
```

Wichtig:

- Original-Strings muessen unveraendert bleiben
- `0.5000` darf nicht zu `0.5` normalisiert werden
- CRC32 wird als signed 32-bit Integer verglichen
- Wenn Bitget auf einem Snapshot `checksum=0` liefert, behandelt der Dienst das
  als "noch nicht verifizierbar" und prueft ab dem ersten non-zero Update
  wieder strikt.

Bei Checksum-Mismatch loggt der Service `orderbook_checksum_mismatch`, markiert
den Book-State als desynchronisiert und triggert den Resync-Pfad
(`books5`-Fallback plus Re-Subscribe).

## Trades / Ticker / REST Fallback

WS:

- `trade`: taker trades mit `ts`, `price`, `size`, `side`, `tradeId`
- `ticker`: `lastPr`, `bidPr`, `askPr`, `markPrice`, `indexPrice`,
  `fundingRate`, `nextFundingTime`, `holdingAmount`

REST Public Snapshots:

- `GET /api/v2/mix/market/open-interest`
- `GET /api/v2/mix/market/current-fund-rate`
- `GET /api/v2/mix/market/symbol-price`

Diese Calls laufen ohne Auth und dienen als Validierung bzw. Fallback fuer OI,
Funding-Details und Symbol-/Mark-/Index-Preis.

## Storage

Migration:

```bash
python infra/migrate.py
```

Tabellen:

- `tsdb.trades`
- `tsdb.ticker`
- `tsdb.orderbook_top25`
- `tsdb.orderbook_levels`
- `tsdb.funding_rate`
- `tsdb.open_interest`

## Redis Output

Slippage-Metriken werden in `stream:market:slippage_metrics` publiziert. Der
Payload enthaelt unter anderem:

- `mid`
- `spread_abs`
- `spread_bps`
- `bid_depth_usdt_topN`
- `ask_depth_usdt_topN`
- `imbalance`
- Buy-/Sell-Impact in BPS fuer konfigurierbare Groessen aus
  `SLIPPAGE_SIZES_USDT`

## Nutzung in der Feature-Pipeline

Seit Prompt 14 nutzt `feature-engine` die TSDB-Snapshots direkt fuer den
kanonischen Modellvertrag:

- `tsdb.orderbook_levels` -> `spread_bps`, Depth, `orderbook_imbalance`,
  `impact_*_bps_*`, `execution_cost_bps`
- `tsdb.funding_rate` -> `funding_rate_bps`, `funding_cost_bps_window`
- `tsdb.open_interest` -> `open_interest`, `open_interest_change_pct`

Wichtig:

- Join-Anker ist `candle_close.exchange_ts_ms`, nicht "latest()" ohne
  Zeitbezug.
- `tsdb.ticker` dient nur als transparenter Fallback fuer Spread/Top-of-Book,
  falls keine L2-Tiefe verfuegbar ist.
- Fehlende Slippage-Proxies werden nicht aufgefuellt; Signal- und Learning-Gates
  sehen diese Luecke explizit ueber `liquidity_source` und `NULL`-Felder.

## WS Betriebsregeln

- Maximal `10` Outbound-Messages pro Sekunde inklusive `ping`,
  `subscribe` und `unsubscribe`
- `ping` laeuft aktiv, eingehende Frames gelten als Liveness-Signal
- Bei Reconnect werden Subscriptions sauber neu aufgebaut
- Keine API-Keys fuer Public-Market-REST loggen oder speichern
