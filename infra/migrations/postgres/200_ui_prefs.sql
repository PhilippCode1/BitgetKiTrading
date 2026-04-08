-- Prompt 25: UI-Preferences (Live-Terminal), keine Secrets

CREATE TABLE IF NOT EXISTS app.ui_preferences (
    pref_id text NOT NULL,
    scope text NOT NULL,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    prefs_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pref_id, scope, symbol)
);

CREATE INDEX IF NOT EXISTS idx_app_ui_prefs_scope_symbol
    ON app.ui_preferences (scope, symbol);
