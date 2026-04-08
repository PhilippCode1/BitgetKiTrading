-- Demo-Seed (nur optionaler Demo-Pfad). Demo-Ticker + Demo-Zeichnung fuer leeren lokalen Stack.
-- Ergaenzt 910; keine Ueberschreibung bestehender Daten.

DO $$
DECLARE
  now_ms bigint;
  d_id uuid;
BEGIN
  now_ms := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint;

  IF NOT EXISTS (SELECT 1 FROM tsdb.ticker WHERE symbol = 'BTCUSDT' LIMIT 1) THEN
    INSERT INTO tsdb.ticker (
      symbol, ts_ms, source, last_pr, bid_pr, ask_pr, mark_price, index_price,
      ingest_ts_ms
    ) VALUES (
      'BTCUSDT', now_ms, 'local_demo_seed',
      50025, 50020, 50030, 50025, 50025,
      now_ms
    );
  END IF;

  IF EXISTS (
    SELECT 1 FROM app.drawings
    WHERE symbol = 'BTCUSDT' AND timeframe = '1m' AND status = 'active'
    LIMIT 1
  ) THEN
    NULL;
  ELSE
    d_id := gen_random_uuid();
    INSERT INTO app.drawings (
      drawing_id, parent_id, revision, symbol, timeframe, type, status,
      geometry_json, style_json, reasons_json, confidence
    ) VALUES (
      d_id, d_id, 1, 'BTCUSDT', '1m', 'demo_zone', 'active',
      '{"kind":"horizontal_zone","price_low":49900,"price_high":50100,"label":"demo_seed"}'::jsonb,
      '{"stroke":"#58a6ff"}'::jsonb,
      '[]'::jsonb,
      50
    );
  END IF;
END $$;
