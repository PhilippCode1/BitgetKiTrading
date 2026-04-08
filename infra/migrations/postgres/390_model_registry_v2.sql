-- Prompt 25: Model Registry V2 (Champion/Challenger, Kalibrierungsstatus)

CREATE TABLE IF NOT EXISTS app.model_registry_v2 (
    registry_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name text NOT NULL,
    role text NOT NULL CHECK (role IN ('champion', 'challenger')),
    run_id uuid NOT NULL REFERENCES app.model_runs (run_id) ON DELETE RESTRICT,
    calibration_status text NOT NULL DEFAULT 'unknown',
    activated_ts timestamptz NOT NULL DEFAULT now(),
    notes text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_model_registry_v2_model_role UNIQUE (model_name, role)
);

CREATE INDEX IF NOT EXISTS idx_model_registry_v2_run
    ON app.model_registry_v2 (run_id);

CREATE INDEX IF NOT EXISTS idx_model_registry_v2_model_role
    ON app.model_registry_v2 (model_name, role);

COMMENT ON TABLE app.model_registry_v2 IS
    'Champion/Challenger Slots je model_name; Produktion laedt Champion wenn MODEL_REGISTRY_V2_ENABLED=true';

-- Bestehende promoted Runs als Champion uebernehmen (idempotent)
INSERT INTO app.model_registry_v2 (model_name, role, run_id, calibration_status, activated_ts)
SELECT DISTINCT ON (mr.model_name)
    mr.model_name,
    'champion',
    mr.run_id,
    CASE
        WHEN mr.model_name IN ('take_trade_prob', 'market_regime_classifier')
            AND (mr.calibration_method IS NULL OR btrim(mr.calibration_method::text) = '')
        THEN 'missing'
        WHEN mr.model_name IN ('take_trade_prob', 'market_regime_classifier')
        THEN 'verified'
        ELSE 'not_applicable'
    END,
    mr.created_ts
FROM app.model_runs mr
WHERE mr.promoted_bool = true
ORDER BY mr.model_name, mr.created_ts DESC
ON CONFLICT (model_name, role) DO NOTHING;
