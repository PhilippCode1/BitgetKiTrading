-- Prompt 70: AI Accuracy Loop — Post-Trade-Reasoning vs. Markt (4h-Fenster)

ALTER TABLE public.ai_evaluation_logs
    ADD COLUMN IF NOT EXISTS source_signal_id uuid NULL;

CREATE INDEX IF NOT EXISTS idx_ai_eval_logs_source_signal
    ON public.ai_evaluation_logs (source_signal_id, created_ts DESC)
    WHERE source_signal_id IS NOT NULL;

COMMENT ON COLUMN public.ai_evaluation_logs.source_signal_id IS
    'Optional: app.signals_v1.signal_id bei strategy_signal_explain (Join wenn execution_id fehlt).';

CREATE TABLE IF NOT EXISTS learn.post_trade_review (
    review_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id uuid NULL,
    execution_id uuid NULL,
    trade_evaluation_id uuid NOT NULL REFERENCES learn.trade_evaluations (evaluation_id) ON DELETE CASCADE,
    scenario_excerpt_de text NULL,
    reference_price numeric NULL,
    reference_role text NULL,
    thesis_holds boolean NULL,
    window_start_ts_ms bigint NOT NULL,
    window_end_ts_ms bigint NOT NULL,
    pnl_net_usdt numeric NOT NULL,
    side text NOT NULL,
    reasoning_accuracy_0_1 double precision NOT NULL,
    quality_label text NOT NULL,
    review_json jsonb NOT NULL,
    attribution_meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_post_trade_review_per_eval UNIQUE (trade_evaluation_id)
);

CREATE INDEX IF NOT EXISTS idx_learn_ptr_signal
    ON learn.post_trade_review (signal_id, created_ts DESC)
    WHERE signal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_learn_ptr_label
    ON learn.post_trade_review (quality_label, created_ts DESC);

COMMENT ON TABLE learn.post_trade_review IS
    'Prompt 70: Abgleich KI-Szenario (strategy_signal_explain) vs. tsdb.candles + P&L; review_json = PostTradeReviewV1.';
