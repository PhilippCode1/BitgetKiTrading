-- End-to-End Lernrecords: Entscheidung, Spezialisten, Outcomes (Paper/Shadow/Live/Counterfactual), QC-Labels

CREATE TABLE IF NOT EXISTS learn.e2e_decision_records (
    record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id uuid NOT NULL REFERENCES app.signals_v1 (signal_id) ON DELETE CASCADE,
    schema_version text NOT NULL DEFAULT 'e2e-v1',
    decision_ts_ms bigint NOT NULL,
    canonical_instrument_id text,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    market_family text NOT NULL DEFAULT 'unknown',
    playbook_id text,
    playbook_family text,
    regime_label text,
    meta_trade_lane text,
    trade_action text,
    paper_trade_id uuid,
    shadow_trade_id uuid,
    live_mirror_trade_id uuid,
    trade_evaluation_id uuid REFERENCES learn.trade_evaluations (evaluation_id) ON DELETE SET NULL,
    snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcomes_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    label_qc_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    operator_mirror_actions_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_e2e_signal UNIQUE (signal_id)
);

CREATE INDEX IF NOT EXISTS idx_e2e_decision_symbol_decision_ts
    ON learn.e2e_decision_records (symbol, decision_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_e2e_decision_market_family_ts
    ON learn.e2e_decision_records (market_family, decision_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_e2e_decision_playbook_ts
    ON learn.e2e_decision_records (playbook_id, decision_ts_ms DESC)
    WHERE playbook_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_e2e_paper_trade
    ON learn.e2e_decision_records (paper_trade_id)
    WHERE paper_trade_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_e2e_trade_evaluation
    ON learn.e2e_decision_records (trade_evaluation_id)
    WHERE trade_evaluation_id IS NOT NULL;

COMMENT ON TABLE learn.e2e_decision_records IS
    'E2E-Lernrecord pro Signal: Spezialisten/Router, Stops, Kontext, Outcomes je Lane (paper/shadow/live/counterfactual), QC-Labels.';

COMMENT ON COLUMN learn.e2e_decision_records.snapshot_json IS
    'Versionierter Entscheidungs-Snapshot (Spezialisten, Risk-Governor, Stop-Budget, SMC, Modellversionen).';

COMMENT ON COLUMN learn.e2e_decision_records.outcomes_json IS
    'Keys: paper, shadow, live_mirror, counterfactual — jeweils Status/Metriken oder null bis bekannt.';

COMMENT ON COLUMN learn.e2e_decision_records.label_qc_json IS
    'QC-/Human-Label-Pfade: false_positive_trade, stop_too_tight, late_entry, poor_exit_selection, manual_override, ...';
