CREATE TABLE IF NOT EXISTS app.instrument_catalog_snapshots (
    snapshot_id uuid PRIMARY KEY,
    source_service text NOT NULL,
    refresh_reason text NOT NULL,
    status text NOT NULL,
    fetch_started_ts_ms bigint NOT NULL,
    fetch_completed_ts_ms bigint,
    refreshed_families_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    counts_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    warnings_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    errors_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.instrument_catalog_entries (
    canonical_instrument_id text PRIMARY KEY,
    snapshot_id uuid NOT NULL REFERENCES app.instrument_catalog_snapshots(snapshot_id) ON DELETE CASCADE,
    venue text NOT NULL,
    market_family text NOT NULL,
    symbol text NOT NULL,
    symbol_aliases_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    product_type text,
    margin_account_mode text NOT NULL,
    margin_coin text,
    base_coin text,
    quote_coin text,
    settle_coin text,
    public_ws_inst_type text NOT NULL,
    private_ws_inst_type text,
    metadata_source text NOT NULL,
    metadata_verified boolean NOT NULL DEFAULT false,
    status text,
    supports_funding boolean NOT NULL DEFAULT false,
    supports_open_interest boolean NOT NULL DEFAULT false,
    supports_long_short boolean NOT NULL DEFAULT false,
    supports_reduce_only boolean NOT NULL DEFAULT false,
    supports_leverage boolean NOT NULL DEFAULT false,
    uses_spot_public_market_data boolean NOT NULL DEFAULT false,
    price_tick_size numeric,
    quantity_step numeric,
    quantity_min numeric,
    min_notional_quote numeric,
    price_precision integer,
    quantity_precision integer,
    quote_precision integer,
    leverage_min integer,
    leverage_max integer,
    trading_status text NOT NULL,
    trading_enabled boolean NOT NULL DEFAULT false,
    subscribe_enabled boolean NOT NULL DEFAULT false,
    session_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    refresh_ts_ms bigint,
    raw_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_instrument_catalog_entries_symbol
    ON app.instrument_catalog_entries (symbol, market_family, product_type);

CREATE INDEX IF NOT EXISTS idx_instrument_catalog_entries_tradeable
    ON app.instrument_catalog_entries (market_family, trading_enabled, subscribe_enabled);

COMMENT ON TABLE app.instrument_catalog_snapshots IS
    'Historisierte Refresh-Snapshots des zentralen Bitget-Instrumentenkatalogs.';

COMMENT ON TABLE app.instrument_catalog_entries IS
    'Aktueller zentraler Instrumentenkatalog fuer Bitget-Instrumente, Marktfamilien und Trading-Capabilities.';
