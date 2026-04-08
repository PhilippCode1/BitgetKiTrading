-- Prompt 12: versionierte Drawings mit symbol, reasons_json, confidence,
-- UNIQUE(parent_id, revision), drawing_id = UUID pro Revision-Zeile.

CREATE TABLE IF NOT EXISTS app.drawings_new (
    drawing_id uuid PRIMARY KEY,
    parent_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision >= 1),
    symbol text NOT NULL,
    timeframe text NOT NULL,
    type text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'hit', 'invalidated', 'expired')),
    geometry_json jsonb NOT NULL,
    style_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence numeric NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    UNIQUE (parent_id, revision)
);

INSERT INTO app.drawings_new (
    drawing_id,
    parent_id,
    revision,
    symbol,
    timeframe,
    type,
    status,
    geometry_json,
    style_json,
    reasons_json,
    confidence,
    created_ts,
    updated_ts
)
SELECT
    drawing_id,
    COALESCE(parent_id, drawing_id),
    GREATEST(revision, 1),
    'BTCUSDT',
    timeframe,
    type,
    CASE
        WHEN status IN ('active', 'hit', 'invalidated', 'expired') THEN status
        ELSE 'expired'
    END,
    geometry_json,
    style_json,
    '[]'::jsonb,
    50,
    created_ts,
    updated_ts
FROM app.drawings;

DROP TABLE IF EXISTS app.drawings;

ALTER TABLE app.drawings_new RENAME TO drawings;

CREATE INDEX IF NOT EXISTS idx_app_drawings_symbol_timeframe_status_updated_desc
    ON app.drawings (symbol, timeframe, status, updated_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_drawings_parent_id_revision_desc
    ON app.drawings (parent_id, revision DESC);

CREATE INDEX IF NOT EXISTS idx_app_drawings_status_updated_ts_desc
    ON app.drawings (status, updated_ts DESC);

CREATE INDEX IF NOT EXISTS idx_app_drawings_geometry_json_gin
    ON app.drawings USING gin (geometry_json);

CREATE INDEX IF NOT EXISTS idx_app_drawings_style_json_gin
    ON app.drawings USING gin (style_json);

CREATE INDEX IF NOT EXISTS idx_app_drawings_reasons_json_gin
    ON app.drawings USING gin (reasons_json);
