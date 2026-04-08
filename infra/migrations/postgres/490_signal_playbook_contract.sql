ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS strategy_name text,
    ADD COLUMN IF NOT EXISTS playbook_id text,
    ADD COLUMN IF NOT EXISTS playbook_family text,
    ADD COLUMN IF NOT EXISTS playbook_decision_mode text,
    ADD COLUMN IF NOT EXISTS playbook_registry_version text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_v1_playbook_decision_mode_check'
    ) THEN
        ALTER TABLE app.signals_v1
            ADD CONSTRAINT signals_v1_playbook_decision_mode_check
            CHECK (
                playbook_decision_mode IS NULL
                OR playbook_decision_mode IN ('selected', 'playbookless')
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_playbook_family_analysis_desc
    ON app.signals_v1 (playbook_family, analysis_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_playbook_id_analysis_desc
    ON app.signals_v1 (playbook_id, analysis_ts_ms DESC);
