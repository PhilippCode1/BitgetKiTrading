-- Prompt 15: News-Ingestion — erweitert app.news_items (020) um Ingestion-Felder
-- Idempotent, bestehende Zeilen (id, url, published_ts) bleiben gueltig.

ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS news_id uuid;
UPDATE app.news_items SET news_id = gen_random_uuid() WHERE news_id IS NULL;
ALTER TABLE app.news_items ALTER COLUMN news_id SET DEFAULT gen_random_uuid();
ALTER TABLE app.news_items ALTER COLUMN news_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_app_news_items_news_id ON app.news_items (news_id);

ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS source_item_id text;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS ingested_ts_ms bigint;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS published_ts_ms bigint;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS description text;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS content text;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS author text;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS language text;

-- published_ts_ms aus published_ts ableiten, wo noch leer
UPDATE app.news_items
SET published_ts_ms = (EXTRACT(EPOCH FROM published_ts) * 1000)::bigint
WHERE published_ts_ms IS NULL AND published_ts IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_app_news_items_source_item
    ON app.news_items (source, source_item_id)
    WHERE source_item_id IS NOT NULL AND btrim(source_item_id) <> '';

CREATE INDEX IF NOT EXISTS idx_app_news_items_ingested_ts_ms_desc
    ON app.news_items (ingested_ts_ms DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_app_news_items_published_ts_ms_desc
    ON app.news_items (published_ts_ms DESC NULLS LAST);
