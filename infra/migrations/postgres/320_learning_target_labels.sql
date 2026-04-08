-- Prompt 15: Learning-Targets fuer Return, Excursions und Liquidationsnaehe

ALTER TABLE learn.trade_evaluations
    ADD COLUMN IF NOT EXISTS decision_ts_ms bigint,
    ADD COLUMN IF NOT EXISTS take_trade_label boolean,
    ADD COLUMN IF NOT EXISTS expected_return_bps numeric,
    ADD COLUMN IF NOT EXISTS expected_return_gross_bps numeric,
    ADD COLUMN IF NOT EXISTS expected_mae_bps numeric,
    ADD COLUMN IF NOT EXISTS expected_mfe_bps numeric,
    ADD COLUMN IF NOT EXISTS liquidation_proximity_bps numeric,
    ADD COLUMN IF NOT EXISTS liquidation_risk boolean;

UPDATE learn.trade_evaluations
SET decision_ts_ms = opened_ts_ms
WHERE decision_ts_ms IS NULL;

ALTER TABLE learn.trade_evaluations
    ALTER COLUMN decision_ts_ms SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_learn_trade_eval_symbol_decision
    ON learn.trade_evaluations (symbol, decision_ts_ms DESC);
