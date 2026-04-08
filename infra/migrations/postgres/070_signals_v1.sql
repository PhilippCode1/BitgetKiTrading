-- Signal Engine V1 (Prompt 13). Neue Tabelle parallel zu Legacy app.signals (demo_trades FK).
CREATE TABLE IF NOT EXISTS app.signals_v1 (
    signal_id uuid PRIMARY KEY,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    analysis_ts_ms bigint NOT NULL,
    market_regime text,
    direction text NOT NULL CHECK (direction IN ('long', 'short', 'neutral')),
    signal_strength_0_100 numeric NOT NULL CHECK (
        signal_strength_0_100 >= 0 AND signal_strength_0_100 <= 100
    ),
    probability_0_1 numeric NOT NULL CHECK (probability_0_1 >= 0 AND probability_0_1 <= 1),
    signal_class text NOT NULL CHECK (signal_class IN ('mikro', 'kern', 'gross', 'warnung')),
    structure_score_0_100 numeric NOT NULL CHECK (
        structure_score_0_100 >= 0 AND structure_score_0_100 <= 100
    ),
    momentum_score_0_100 numeric NOT NULL CHECK (
        momentum_score_0_100 >= 0 AND momentum_score_0_100 <= 100
    ),
    multi_timeframe_score_0_100 numeric NOT NULL CHECK (
        multi_timeframe_score_0_100 >= 0 AND multi_timeframe_score_0_100 <= 100
    ),
    news_score_0_100 numeric NOT NULL CHECK (news_score_0_100 >= 0 AND news_score_0_100 <= 100),
    risk_score_0_100 numeric NOT NULL CHECK (risk_score_0_100 >= 0 AND risk_score_0_100 <= 100),
    history_score_0_100 numeric NOT NULL CHECK (
        history_score_0_100 >= 0 AND history_score_0_100 <= 100
    ),
    weighted_composite_score_0_100 numeric NOT NULL CHECK (
        weighted_composite_score_0_100 >= 0 AND weighted_composite_score_0_100 <= 100
    ),
    rejection_state boolean NOT NULL DEFAULT false,
    rejection_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    decision_state text NOT NULL CHECK (
        decision_state IN ('accepted', 'downgraded', 'rejected')
    ),
    reasons_json jsonb NOT NULL,
    supporting_drawing_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    supporting_structure_event_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    stop_zone_id uuid,
    target_zone_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    reward_risk_ratio numeric,
    expected_volatility_band numeric,
    source_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    scoring_model_version text NOT NULL,
    signal_components_history_json jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_symbol_tf_analysis_desc
    ON app.signals_v1 (symbol, timeframe, analysis_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_symbol_tf_created_desc
    ON app.signals_v1 (symbol, timeframe, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_decision_state
    ON app.signals_v1 (decision_state, analysis_ts_ms DESC);
