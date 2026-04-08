-- Signal V1: family-aware Regime-State + Instrument-Identity fuer Persistenz/Hysterese

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS canonical_instrument_id text,
    ADD COLUMN IF NOT EXISTS market_family text,
    ADD COLUMN IF NOT EXISTS regime_state text,
    ADD COLUMN IF NOT EXISTS regime_substate text,
    ADD COLUMN IF NOT EXISTS regime_transition_state text,
    ADD COLUMN IF NOT EXISTS regime_transition_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS regime_persistence_bars integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS regime_policy_version text;

UPDATE app.signals_v1
SET market_family = COALESCE(NULLIF(market_family, ''), 'unknown')
WHERE market_family IS NULL OR market_family = '';

UPDATE app.signals_v1
SET canonical_instrument_id = COALESCE(
        NULLIF(canonical_instrument_id, ''),
        'bitget:unknown:unknown:' || symbol
    )
WHERE canonical_instrument_id IS NULL OR canonical_instrument_id = '';

UPDATE app.signals_v1
SET regime_state = COALESCE(NULLIF(regime_state, ''), market_regime)
WHERE regime_state IS NULL OR regime_state = '';

UPDATE app.signals_v1
SET regime_substate = COALESCE(NULLIF(regime_substate, ''), regime_state || '_legacy')
WHERE regime_substate IS NULL OR regime_substate = '';

UPDATE app.signals_v1
SET regime_transition_state = COALESCE(NULLIF(regime_transition_state, ''), 'stable')
WHERE regime_transition_state IS NULL OR regime_transition_state = '';

ALTER TABLE app.signals_v1
    ALTER COLUMN market_family SET NOT NULL,
    ALTER COLUMN canonical_instrument_id SET NOT NULL,
    ALTER COLUMN regime_state SET NOT NULL,
    ALTER COLUMN regime_substate SET NOT NULL,
    ALTER COLUMN regime_transition_state SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_v1_regime_transition_state_check'
    ) THEN
        ALTER TABLE app.signals_v1
            ADD CONSTRAINT signals_v1_regime_transition_state_check
            CHECK (
                regime_transition_state IN (
                    'stable',
                    'entering',
                    'switch_confirmed',
                    'sticky_hold',
                    'switch_immediate'
                )
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_canonical_tf_analysis_desc
    ON app.signals_v1 (canonical_instrument_id, timeframe, analysis_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_regime_state_analysis_desc
    ON app.signals_v1 (regime_state, analysis_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_regime_transition_analysis_desc
    ON app.signals_v1 (regime_transition_state, analysis_ts_ms DESC);
