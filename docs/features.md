# Features

## Ziel

`feature-engine` baut einen kanonischen, einfrierbaren Feature-Snapshot pro
geschlossener Candle. Der Snapshot ist family-aware, aber weiterhin
vergleichbar genug, damit Family-Spezialisten, Regime-Spezialisten,
Microstructure-Gates, Router und spaeter Learning-/Meta-Layer auf denselben
Rohvertrag schauen.

Der Produktionspfad ist bewusst deterministisch:

- Input-Stream: `events:candle_close`
- Event muss eine `instrument`-Identity tragen
- Primäre Candle-Quelle: `tsdb.candles`
- Markt-Kontext as-of `exchange_ts_ms` bzw. Candle-Close
- Persistenzziel: `features.candle_features`

Die Persistenz ist ab der Family-Schema-Migration nicht mehr rein symbolbasiert:
Upserts und Primärschluessel laufen ueber
`(canonical_instrument_id, timeframe, start_ts_ms)`. Reine Symbol-Lookups
bleiben als Komfort-API erhalten, sind aber fuer gleichlautende Symbole ueber
mehrere Families hinweg nicht mehr der kanonische Identitaetsanker.

## Kanonisches Schema

Quelle der Wahrheit: `shared_py.model_contracts`

- `FEATURE_SCHEMA_VERSION = 3.0`
- `FEATURE_SCHEMA_HASH`: stabiler Hash ueber den Snapshot-Feldsatz
- `FEATURE_FIELD_CATALOG_VERSION` / `FEATURE_FIELD_CATALOG_HASH`: separater
  Katalog fuer Feature-Gruppen, Family-Scope und Spezialisten-Zielgruppe

### Gruppen

| Gruppe           | Zweck                                                                          | Familien                  | Typische Nutzer                 |
| ---------------- | ------------------------------------------------------------------------------ | ------------------------- | ------------------------------- |
| `identity`       | Instrument-, Family- und Snapshot-Identitaet                                   | alle                      | Router, Meta, Audit             |
| `core`           | family-uebergreifende Candle-, Trend- und Volatilitaetsmerkmale                | alle                      | Family-, Regime-, Meta-Layer    |
| `microstructure` | Spread, Depth, Impact, Imbalance, Ausfuehrungskosten                           | alle mit Orderbook/Ticker | Microstructure-/Execution-Gates |
| `family`         | Futures-only Kontext wie Funding, Basis, Mark-vs-Index, OI, Liquidations-Proxy | nur `futures`             | Family-Spezialisten, Risk       |
| `quality`        | Completeness, Staleness, Gap- und Source-Semantik                              | alle                      | harte Quality-/No-Trade-Gates   |

### Wichtige persistierte Identitaetsfelder

- `canonical_instrument_id`
- `market_family`
- `product_type`
- `margin_account_mode`
- `instrument_metadata_snapshot_id`
- `symbol`
- `timeframe`
- `start_ts_ms`

## Feature-Gruppen im Detail

### Core

- `atr_14`, `atrp_14`, `rsi_14`, `ret_1`, `ret_5`, `momentum_score`
- `impulse_*`, `range_score`, `trend_ema_fast`, `trend_ema_slow`,
  `trend_slope_proxy`, `trend_dir`
- `confluence_score_0_100`, `vol_z_50`
- `session_drift_bps`: Drift relativ zu einem timeframe-sensitiven Session-Horizont
- `breakout_compression_score_0_100`: Kompressions-/Breakout-Readiness aus
  Range, ATR-Prozent und Tiefe
- `realized_vol_cluster_0_100`: kurzer vs. laengerer RV-Cluster als
  Regime-Hinweis

### Microstructure

- `spread_bps`
- `bid_depth_usdt_top25`, `ask_depth_usdt_top25`
- `orderbook_imbalance`, `depth_balance_ratio`, `depth_to_bar_volume_ratio`
- `impact_*_bps_*`, `execution_cost_bps`, `volatility_cost_bps`
- `spread_persistence_bps`: gleitender Spread-Proxy ueber juengste Ticker-Snapshots
- `mean_reversion_pressure_0_100`: Drift-vs-EMA plus gegenlaeufiger Flow

### Family

Nur dort befuellt, wo die Family fachlich passt. Fuer nicht passende Familien
bleiben die Werte `NULL`, und die Sources werden auf `not_applicable` gesetzt.

Futures:

- `funding_rate`, `funding_rate_bps`, `funding_cost_bps_window`
- `funding_time_to_next_ms`
- `open_interest`, `open_interest_change_pct`
- `mark_index_spread_bps`
- `basis_bps`
- `liquidation_distance_bps_max_leverage`
- `event_distance_ms`: naechstes Funding-/Maintenance-/Delivery-Ereignis

Spot / Margin:

- Funding-/OI-/Mark-vs-Index-Felder werden **nicht** synthetisch gefuellt
- stattdessen greifen `session_drift_bps`, `spread_persistence_bps`,
  `mean_reversion_pressure_0_100`, `breakout_compression_score_0_100`,
  `orderbook_imbalance` und `realized_vol_cluster_0_100`

## Missing-Value-Semantik

- `NULL` + `source=missing`: Datentyp fachlich sinnvoll, aber as-of nicht verfuegbar
- `NULL` + `source=not_applicable`: Family/Instrument macht das Feld ungueltig
- `market_family=unknown`: nur Legacy-/Altdatenpfad fuer vor-Schema-3.0-Snapshots;
  neuer Produktionspfad soll immer eine echte Instrument-Identity liefern

## Quality- und As-of-Modell

- `data_completeness_0_1`: Wie viel des fuer die Family **und Capabilities**
  erwarteten Kontexts zum Analysezeitpunkt vorhanden war (Futures ohne OI-Capability
  bestraft fehlendes OI nicht)
- `staleness_score_0_1`: normalisierte Frische; Funding/OI-Anteile nur bei passender Capability
- `gap_count_lookback`: Gaps im Candle-Lookback
- `feature_quality_status`: `ok` oder `degraded`
- `pipeline_trade_mode` (in `auxiliary_inputs`): `ok` | `analytics_only` | `do_not_trade`
  — Steuersignal fuer den Handelskern bei Metadata-/Leak-/Qualitaetslage
- Explizite Feature-Namensraeume: `feature_namespaces`, `feature_namespace_bundle_version`
  (siehe `shared_py.analysis`)
- `input_provenance_json`: as-of-, Gap-, Warmup- und Hilfsdaten fuer Audit und
  Training/Inference-Paritaet

Architektur-Ueberblick: `docs/analysis_data_path.md`.

Wichtig:

- Futures-only Felder werden fuer Spot/Margin nicht mit Scheinwerten belegt
- fehlende Ticker-/Book-Daten fuehren nicht zu impliziten Defaults
- Metadata-Degradationen (`instrument_metadata_snapshot_id`,
  Katalog-Health, Session-Windows) fliessen in den Quality-Status ein

## Worker-Verhalten

- Consumer Group: `feature-engine`
- Erfolgreicher Upsert -> `XACK`
- Fehler beim Processing -> `events:dlq`, danach `XACK`
- Hartes Reject vor Persistenz bei kaputten Candle-Events
  (`instrument_missing`, OHLC-Inkonsistenz, nicht-negative Volumina, stale input)
- Feature-Berechnung nutzt den Instrumentenkatalog fuer Family-, Session- und
  Leverage-Kontext
- Multi-TF-Konfluenz liest bevorzugt `canonical_instrument_id`, damit
  Family-uebergreifende Symbolgleichheit nicht blind zusammengezogen wird

## API

- `GET /health`
- `GET /ready`
- `GET /features/latest?symbol=<example_symbol>&timeframe=1m`
- `GET /features/latest?symbol=<example_symbol>&timeframe=1m&market_family=<example_family>&canonical_instrument_id=<example_canonical_instrument_id>`
- `GET /features/at?symbol=<example_symbol>&timeframe=1m&start_ts_ms=...`

## Beispiel-Output

```json
{
  "status": "ok",
  "feature": {
    "canonical_instrument_id": "<example_canonical_instrument_id>",
    "market_family": "<example_family>",
    "symbol": "<example_symbol>",
    "timeframe": "5m",
    "start_ts_ms": 1700000000000,
    "mark_index_spread_bps": 1.4,
    "basis_bps": 2.2,
    "session_drift_bps": 18.0,
    "spread_persistence_bps": 1.8,
    "mean_reversion_pressure_0_100": 42.0,
    "data_completeness_0_1": 0.92,
    "staleness_score_0_1": 0.12,
    "feature_quality_status": "ok",
    "feature_schema_version": "3.0"
  }
}
```
