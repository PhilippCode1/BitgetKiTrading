ALTER TABLE app.instrument_catalog_snapshots
    ADD COLUMN IF NOT EXISTS capability_matrix_json jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE app.instrument_catalog_entries
    ADD COLUMN IF NOT EXISTS category_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS inventory_visible boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS analytics_eligible boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS paper_shadow_eligible boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS live_execution_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS execution_disabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS supports_shorting boolean NOT NULL DEFAULT false;

UPDATE app.instrument_catalog_entries
SET category_key = COALESCE(
        NULLIF(category_key, ''),
        venue || ':' || market_family || ':' || COALESCE(product_type, margin_account_mode)
    ),
    inventory_visible = true,
    analytics_eligible = COALESCE(subscribe_enabled, false),
    paper_shadow_eligible = COALESCE(trading_enabled, false),
    live_execution_enabled = COALESCE(trading_enabled, false),
    execution_disabled = COALESCE(subscribe_enabled, false) AND NOT COALESCE(trading_enabled, false),
    supports_shorting = COALESCE(supports_shorting, supports_long_short, false);

CREATE INDEX IF NOT EXISTS idx_instrument_catalog_entries_category_key
    ON app.instrument_catalog_entries (category_key);

CREATE INDEX IF NOT EXISTS idx_instrument_catalog_entries_eligibility
    ON app.instrument_catalog_entries (
        market_family,
        analytics_eligible,
        paper_shadow_eligible,
        live_execution_enabled
    );
