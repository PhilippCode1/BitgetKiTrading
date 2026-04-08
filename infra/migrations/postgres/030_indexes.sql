CREATE INDEX IF NOT EXISTS idx_tsdb_candles_symbol_timeframe_start_desc
    ON tsdb.candles (symbol, timeframe, start_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_candles_ingest_ts_ms_desc
    ON tsdb.candles (ingest_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_trades_symbol_ts_ms_desc
    ON tsdb.trades (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_ticker_symbol_ts_ms_desc
    ON tsdb.ticker (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_top25_symbol_ts_ms_desc
    ON tsdb.orderbook_top25 (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_top25_symbol_seq_desc
    ON tsdb.orderbook_top25 (symbol, seq DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_levels_symbol_ts_ms_desc
    ON tsdb.orderbook_levels (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_orderbook_levels_symbol_side_level
    ON tsdb.orderbook_levels (symbol, side, level);

CREATE INDEX IF NOT EXISTS idx_tsdb_funding_rate_symbol_ts_ms_desc
    ON tsdb.funding_rate (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tsdb_open_interest_symbol_ts_ms_desc
    ON tsdb.open_interest (symbol, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_news_items_published_ts_desc
    ON app.news_items (published_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_news_items_raw_json_gin
    ON app.news_items USING gin (raw_json);

CREATE INDEX IF NOT EXISTS idx_app_news_items_llm_summary_json_gin
    ON app.news_items USING gin (llm_summary_json);

CREATE INDEX IF NOT EXISTS idx_app_drawings_status_updated_ts_desc
    ON app.drawings (status, updated_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_drawings_geometry_json_gin
    ON app.drawings USING gin (geometry_json);

CREATE INDEX IF NOT EXISTS idx_app_drawings_style_json_gin
    ON app.drawings USING gin (style_json);

CREATE INDEX IF NOT EXISTS idx_app_signals_state_created_ts_desc
    ON app.signals (state, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_signals_reasons_json_gin
    ON app.signals USING gin (reasons_json);

CREATE INDEX IF NOT EXISTS idx_app_signals_targets_json_gin
    ON app.signals USING gin (targets_json);

CREATE INDEX IF NOT EXISTS idx_app_demo_trades_state_opened_ts_desc
    ON app.demo_trades (state, opened_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_demo_trades_fills_json_gin
    ON app.demo_trades USING gin (fills_json);

CREATE INDEX IF NOT EXISTS idx_app_strategy_versions_status_created_ts_desc
    ON app.strategy_versions (status, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_strategy_versions_definition_json_gin
    ON app.strategy_versions USING gin (definition_json);

CREATE INDEX IF NOT EXISTS idx_app_model_runs_model_name_created_ts_desc
    ON app.model_runs (model_name, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_model_runs_metrics_json_gin
    ON app.model_runs USING gin (metrics_json);

CREATE INDEX IF NOT EXISTS idx_app_audit_log_entity_created_ts_desc
    ON app.audit_log (entity_schema, entity_table, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_audit_log_payload_gin
    ON app.audit_log USING gin (payload);
