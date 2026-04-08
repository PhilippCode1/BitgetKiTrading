-- Prompt 17: News-Scoring — Spalten, Typ-Migration (relevance int, sentiment text), Index

ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS impact_window text;
UPDATE app.news_items SET impact_window = 'unknown' WHERE impact_window IS NULL;
ALTER TABLE app.news_items ALTER COLUMN impact_window SET DEFAULT 'unknown';
ALTER TABLE app.news_items ALTER COLUMN impact_window SET NOT NULL;

ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS scored_ts_ms bigint;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS scoring_version text;
ALTER TABLE app.news_items ADD COLUMN IF NOT EXISTS entities_json jsonb;

-- relevance_score: numeric -> integer 0..100, NOT NULL default 0
DO $$
DECLARE
  dt regtype;
BEGIN
  SELECT a.atttypid::regtype INTO dt
  FROM pg_attribute a
  JOIN pg_class c ON a.attrelid = c.oid
  JOIN pg_namespace n ON c.relnamespace = n.oid
  WHERE n.nspname = 'app'
    AND c.relname = 'news_items'
    AND a.attname = 'relevance_score'
    AND NOT a.attisdropped
    AND a.attnum > 0;

  IF dt IS NULL THEN
    ALTER TABLE app.news_items ADD COLUMN relevance_score integer NOT NULL DEFAULT 0;
  ELSIF dt::text IN ('numeric', 'double precision', 'real') THEN
    ALTER TABLE app.news_items
      ALTER COLUMN relevance_score TYPE integer USING LEAST(
        100,
        GREATEST(0, COALESCE(ROUND(relevance_score::numeric), 0)::integer)
      );
    ALTER TABLE app.news_items ALTER COLUMN relevance_score SET DEFAULT 0;
    UPDATE app.news_items SET relevance_score = 0 WHERE relevance_score IS NULL;
    ALTER TABLE app.news_items ALTER COLUMN relevance_score SET NOT NULL;
  ELSIF dt::text = 'integer' THEN
    UPDATE app.news_items SET relevance_score = 0 WHERE relevance_score IS NULL;
    ALTER TABLE app.news_items ALTER COLUMN relevance_score SET DEFAULT 0;
    ALTER TABLE app.news_items ALTER COLUMN relevance_score SET NOT NULL;
  END IF;
END$$;

-- sentiment: numeric -> text (bullisch / baerisch / neutral / unknown)
DO $$
DECLARE
  dt regtype;
BEGIN
  SELECT a.atttypid::regtype INTO dt
  FROM pg_attribute a
  JOIN pg_class c ON a.attrelid = c.oid
  JOIN pg_namespace n ON c.relnamespace = n.oid
  WHERE n.nspname = 'app'
    AND c.relname = 'news_items'
    AND a.attname = 'sentiment'
    AND NOT a.attisdropped
    AND a.attnum > 0;

  IF dt IS NULL THEN
    ALTER TABLE app.news_items ADD COLUMN sentiment text NOT NULL DEFAULT 'unknown';
  ELSIF dt::text IN ('numeric', 'double precision', 'real') THEN
    ALTER TABLE app.news_items ADD COLUMN sentiment_text_mig text;
    UPDATE app.news_items SET sentiment_text_mig = CASE
      WHEN sentiment IS NULL THEN 'unknown'
      WHEN sentiment > 0.2::numeric THEN 'bullisch'
      WHEN sentiment < -0.2::numeric THEN 'baerisch'
      ELSE 'neutral'
    END;
    ALTER TABLE app.news_items DROP COLUMN sentiment;
    ALTER TABLE app.news_items RENAME COLUMN sentiment_text_mig TO sentiment;
    ALTER TABLE app.news_items ALTER COLUMN sentiment SET DEFAULT 'unknown';
    ALTER TABLE app.news_items ALTER COLUMN sentiment SET NOT NULL;
  ELSIF dt::text IN ('text', 'character varying') THEN
    UPDATE app.news_items SET sentiment = 'unknown' WHERE sentiment IS NULL;
    ALTER TABLE app.news_items ALTER COLUMN sentiment SET DEFAULT 'unknown';
    ALTER TABLE app.news_items ALTER COLUMN sentiment SET NOT NULL;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_app_news_items_relevance_published
  ON app.news_items (relevance_score DESC, published_ts_ms DESC NULLS LAST);
