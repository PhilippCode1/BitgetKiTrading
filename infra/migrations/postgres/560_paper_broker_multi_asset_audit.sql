-- Paper-Broker: Multi-Asset-Metadaten auf Positionen, erweiterte Strategy-Audit-Event-Typen.
-- Fix: Code verwendete AUTO_BLOCKED ohne CHECK-Erlaubnis.

ALTER TABLE paper.positions
    ADD COLUMN IF NOT EXISTS signal_id uuid,
    ADD COLUMN IF NOT EXISTS canonical_instrument_id text,
    ADD COLUMN IF NOT EXISTS market_family text,
    ADD COLUMN IF NOT EXISTS product_type text;

CREATE INDEX IF NOT EXISTS idx_paper_positions_signal_id
    ON paper.positions (signal_id)
    WHERE signal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_paper_positions_canonical_instrument
    ON paper.positions (canonical_instrument_id)
    WHERE canonical_instrument_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_paper_positions_market_family
    ON paper.positions (market_family, state)
    WHERE market_family IS NOT NULL;

ALTER TABLE paper.strategy_events DROP CONSTRAINT IF EXISTS strategy_events_type_check;
ALTER TABLE paper.strategy_events DROP CONSTRAINT IF EXISTS paper_strategy_events_type_check;

ALTER TABLE paper.strategy_events ADD CONSTRAINT strategy_events_type_check CHECK (
    type IN (
        'AUTO_OPEN',
        'AUTO_CLOSE',
        'NEWS_SHOCK',
        'DRAWING_TP_UPDATE',
        'STRUCTURE_FLIP_EXIT',
        'AUTO_BLOCKED',
        'NO_TRADE_GATE',
        'PLAN_SNAPSHOT',
        'POST_TRADE_REVIEW_READY'
    )
);
