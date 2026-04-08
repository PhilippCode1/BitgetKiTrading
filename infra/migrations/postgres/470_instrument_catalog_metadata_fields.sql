ALTER TABLE app.instrument_catalog_entries
    ADD COLUMN IF NOT EXISTS quantity_max numeric,
    ADD COLUMN IF NOT EXISTS market_order_quantity_max numeric,
    ADD COLUMN IF NOT EXISTS funding_interval_hours integer,
    ADD COLUMN IF NOT EXISTS symbol_type text,
    ADD COLUMN IF NOT EXISTS supported_margin_coins_json jsonb NOT NULL DEFAULT '[]'::jsonb;
