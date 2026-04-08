-- Demo-Seed (nur bei BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true via infra/migrate.py --demo-seeds).
-- Minimaler Platzhalter fuer leeren lokalen Stack (Kerzen + News).
-- Ergaenzung Ticker/Zeichnung: 911_demo_local_ticker_drawings.sql
-- Nur wenn die jeweilige Tabelle noch keine Zeile hat — keine Ueberschreibung bestehender Daten.

DO $$
DECLARE
  now_ms bigint;
  bar_open bigint;
BEGIN
  IF EXISTS (SELECT 1 FROM tsdb.candles LIMIT 1) THEN
    NULL;
  ELSE
    now_ms := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint;
    bar_open := now_ms - (now_ms % 60000) - 60000;

    INSERT INTO tsdb.candles (
      symbol, timeframe, start_ts_ms, open, high, low, close,
      base_vol, quote_vol, usdt_vol, ingest_ts_ms
    ) VALUES (
      'BTCUSDT', '1m', bar_open,
      50000, 50100, 49950, 50025,
      1, 50025, 50025, now_ms
    );
  END IF;

  IF EXISTS (SELECT 1 FROM app.news_items LIMIT 1) THEN
    NULL;
  ELSE
    now_ms := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint;
    INSERT INTO app.news_items (
      source, source_item_id, title, url, published_ts, relevance_score, raw_json,
      ingested_ts_ms, published_ts_ms
    ) VALUES (
      'local_demo_seed',
      'local_demo_seed_v1',
      'Demo: Platzhalter-News fuer lokalen Stack',
      'https://bitget-btc-ai.local/demo-news-placeholder-' || substr(md5(random()::text), 1, 12),
      clock_timestamp(),
      50,
      '{"seed": true, "note_de": "Automatisch eingefuegt wenn news_items leer; durch echte News ersetzt."}'::jsonb,
      now_ms,
      now_ms
    );
  END IF;
END $$;
