-- Prompt 11: Vollstaendigkeit und Alter der Pipeline-Inputs fuer Downstream-Consumer.

ALTER TABLE features.candle_features
    ADD COLUMN IF NOT EXISTS input_provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE app.structure_state
    ADD COLUMN IF NOT EXISTS input_provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE app.drawings
    ADD COLUMN IF NOT EXISTS input_provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN features.candle_features.input_provenance_json IS
    'Luecken/Warmup, Hilfssignale (ret_10, realized_vol), Alter von OB/Funding/OI; pipeline_version siehe JSON.';

COMMENT ON COLUMN app.structure_state.input_provenance_json IS
    'Candle-Luecken, Gates fuer BOS/CHOCH und False-Breakout-Watch; pipeline_version siehe JSON.';

COMMENT ON COLUMN app.drawings.input_provenance_json IS
    'Freshness Orderbook vs. Bar, geerbte Structure-Candle-Metriken; pipeline_version siehe JSON.';
