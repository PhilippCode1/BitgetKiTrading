-- Prompt 22: Meta-Trade-Lane (Ausfuehrungsstufe nach kalibrierter take_trade_prob-Schicht).

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS meta_trade_lane text;

COMMENT ON COLUMN app.signals_v1.meta_trade_lane IS
    'do_not_trade | shadow_only | paper_only | candidate_for_live; Hybrid/Meta vs. Safety-Layer siehe docs/meta_trade_decision.md';

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_meta_trade_lane
    ON app.signals_v1 (analysis_ts_ms DESC, meta_trade_lane);
