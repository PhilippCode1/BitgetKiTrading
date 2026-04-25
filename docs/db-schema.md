# DB Schema

## Zielbild

Ab Prompt 8 ist `infra/migrations/postgres` die kanonische Quelle fuer das
relationale Schema. **`infra/migrate.py`** wendet Dateien in Reihenfolge
**numerisches Praefix (Zahl), dann Dateiname** an (nicht rein lexikographisch),
und protokolliert in `app.schema_migrations` pro **Dateiname** — doppelte
Praefixe (z. B. zwei `550_*.sql`) sind erlaubt, sofern die alphabetische
Reihenfolge der Namen der Abhaengigkeit entspricht.

**Demo-Seed (nur lokal, optional):** `infra/migrations/postgres_demo/912_demo_local_learning_registry_seed.sql`
(wird nur mit `BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true` und `migrate.py --demo-seeds` angewendet).
Die Dateien `596`/`597`/`603` unter `postgres/` bleiben als **No-Op** fuer `schema_migrations`-Kontinuitaet.
Siehe `docs/migrations.md` (Demo-Seeds, `postgres_demo/`).

Die Datenbank trennt u. a.:

- `tsdb`: Time-Series Markt- und Microstructure-Daten
- `app`: Domain-Objekte, Versionierung, Audit und Migration-Tracking
- `paper`: Paper-Broker (Prompt 18) — simulierte Accounts, Positionen, Fills, Ledger

## Warum `numeric`

Bitget liefert Preise, Funding-Rates und Volumen als String-Werte. Diese Daten
werden in Postgres als `numeric` gespeichert, nicht als `float`, damit:

- keine Precision-Drift bei Preisen und Volumen entsteht
- Funding- und PnL-Berechnungen reproduzierbar bleiben
- Orderbook-/Checksum-nahe Daten spaeter nachvollziehbar bleiben

Die Original-Stringform fuer das Orderbook bleibt zusaetzlich in
`tsdb.orderbook_top25` als `jsonb` erhalten.

## ER-Uebersicht

`tsdb`:

- `tsdb.candles`
- `tsdb.trades`
- `tsdb.ticker`
- `tsdb.orderbook_top25`
- `tsdb.orderbook_levels`
- `tsdb.funding_rate`
- `tsdb.open_interest`

`app`:

- `app.schema_migrations`
- `app.news_items`
- `app.drawings`
- `app.signals`
- `app.demo_trades`
- `app.strategy_versions`
- `app.model_runs`
- `app.model_registry_v2` (Champion/Challenger-Slots, Migrationen `390`, `550` scoped slots)
- `app.audit_log`
- `app.admin_rules` (Prompt 26, Schwellen/Weightings)

`paper` (Migration `110_paper_broker_core.sql`):

- `paper.accounts`, `paper.positions`, `paper.orders`, `paper.fills`
- `paper.fee_ledger`, `paper.funding_ledger`, `paper.contract_config_snapshots`

Siehe `docs/paper_broker.md`.

`alert` (Migration `230_alert_engine.sql`, Prompt 27):

- `alert.bot_state`, `alert.chat_subscriptions`, `alert.alert_outbox`, `alert.dedupe_keys`,
  `alert.command_audit`, `alert.structure_trend_state`,
  `alert.telegram_operator_pending`, `alert.operator_action_audit` (Migration `581_alert_telegram_operator_governance.sql`)

Siehe `docs/alert_engine.md`.

Wichtige Beziehungen:

- `app.demo_trades.signal_id` referenziert `app.signals.signal_id`
- `app.drawings` ist revisionsbasiert ueber `(drawing_id, revision)`
- `app.strategy_versions` ist versionsbasiert ueber `(strategy_id, version)`

## Tabellenliste

### `tsdb.candles`

- PK: `(symbol, timeframe, start_ts_ms)`
- Zweck: persistente Candles aus Bitget WS/REST
- Kernfelder: `open`, `high`, `low`, `close`, `base_vol`, `quote_vol`,
  `usdt_vol`, `ingest_ts_ms`

### `tsdb.trades`

- PK: `(symbol, trade_id)`
- Zweck: taker trades aus dem WS-Channel `trade`
- Kernfelder: `ts_ms`, `price`, `size`, `side`

### `tsdb.ticker`

- PK: `(symbol, ts_ms)`
- Zweck: kombinierte Snapshot-Sicht fuer Ticker/Mark/Index/Funding/OI
- Kernfelder: `last_pr`, `bid_pr`, `ask_pr`, `mark_price`, `index_price`,
  `funding_rate`, `next_funding_time_ms`, `holding_amount`

### `tsdb.orderbook_top25`

- PK: `(symbol, ts_ms)`
- Zweck: Audit- und Replay-Sicht fuer Top-25-Orderbook samt Checksum
- Kernfelder: `seq`, `checksum`, `bids_raw`, `asks_raw`

### `tsdb.orderbook_levels`

- PK: `(symbol, ts_ms, side, level)`
- Zweck: abgeflachte Query-Sicht fuer Top-N-Level

### `tsdb.funding_rate`

- PK: `(symbol, ts_ms)`
- Zweck: Funding-Snapshots aus REST/WS
- Kernfelder: `funding_rate`, `interval_hours`, `next_update_ms`, `min_rate`,
  `max_rate`

### `tsdb.open_interest`

- PK: `(symbol, ts_ms)`
- Zweck: OI-Snapshots aus REST/WS
- Kernfeld: `size`

### `app.news_items`

- PK: `id` (bigserial); zusaetzlich eindeutiges `news_id` (uuid, Migration 090)
- Zweck: rohe News plus angereicherte LLM-Zusammenfassung; Ingestion-Felder
  (`source_item_id`, `published_ts_ms`, `ingested_ts_ms`, …) siehe `090_news_items.sql`
- Scoring (Migration `100_news_scoring.sql`): `relevance_score` (int), `sentiment` (text),
  `impact_window`, `scored_ts_ms`, `scoring_version`, `entities_json`; siehe `docs/news_scoring.md`

### `app.drawings`

- PK: `(drawing_id, revision)`
- Zweck: versionierte Chart-Objekte

### `app.signals`

- PK: `signal_id`
- Zweck: generierte Trading-Signale mit Gruenden und Ziel-/Stop-Struktur

### `app.demo_trades`

- PK: `paper_trade_id`
- Zweck: Paper-Trading-Lebenszyklus inklusive Fees, Funding und PnL

### `app.strategy_versions`

- PK: `(strategy_id, version)`
- Zweck: versionierte Strategie-Definitionen

### `app.model_runs`

- PK: `run_id`
- Zweck: Modell-Laeufe, Metriken und Promotion-Status

### `app.model_registry_v2`

- UNIQUE: `(model_name, role, scope_type, scope_key)` mit `role` in (`champion`, `challenger`);
  `scope_type` / `scope_key` seit Migration `550_model_registry_v2_scoped_slots.sql`
  (`global` + leerer Key = bisheriges Verhalten).
- FK: `run_id` → `app.model_runs`
- Zweck: welcher Run in Produktion (Champion) bzw. Shadow (Challenger) aktiv ist;
  `calibration_status`, `activated_ts`; Verknuepfung zu Run-Metadaten

### `app.audit_log`

- PK: `audit_id`
- Zweck: write-ahead Audit fuer Domain-Aenderungen

### `app.admin_rules`

- PK: `rule_set_id`
- Zweck: nicht-sensible Regelsets (`rules_json`) fuer Dashboard Admin; Migration `210_admin_rules_store.sql`

## Schema `learn` (Auszug — Backtest, Prompt 24)

### `learn.online_drift_state`

- PK: `scope` (z. B. `global`)
- Zweck: materialisierter Online-Drift fuer Live-/Signal-Gates (Prompt 26); Migration `400_online_drift_state.sql`
- Felder u. a.: `effective_action` (`ok` \| `warn` \| `shadow_only` \| `hard_block`), `computed_at`, `lookback_minutes`, `breakdown_json`

### `learn.backtest_runs`

- PK: `run_id`
- Offline/Replay-Metadaten, `cv_method`, `metrics_json`, `status`

### `learn.backtest_folds`

- FK: `run_id` → `learn.backtest_runs`
- Train/Test-Zeitgrenzen + `metrics_json` pro Fold

### `learn.replay_sessions`

- PK: `session_id`
- Replay-Zeitraum, `speed_factor`, `status`
