-- Meta-Decision-Kernel: finale Aktionssemantik, Audit-Bundle, Operator-Override nur separat.
ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS meta_decision_action text NOT NULL DEFAULT 'do_not_trade',
    ADD COLUMN IF NOT EXISTS meta_decision_kernel_version text,
    ADD COLUMN IF NOT EXISTS meta_decision_bundle_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS operator_override_audit_json jsonb;

ALTER TABLE app.signals_v1
    DROP CONSTRAINT IF EXISTS signals_v1_meta_decision_action_check;

ALTER TABLE app.signals_v1
    ADD CONSTRAINT signals_v1_meta_decision_action_check CHECK (
        meta_decision_action IN (
            'do_not_trade',
            'allow_trade_candidate',
            'candidate_for_live',
            'operator_release_pending',
            'blocked_by_policy'
        )
    );

COMMENT ON COLUMN app.signals_v1.meta_decision_action IS
    'Finale Kernel-Aktion: do_not_trade | allow_trade_candidate | candidate_for_live | operator_release_pending | blocked_by_policy';

COMMENT ON COLUMN app.signals_v1.meta_decision_kernel_version IS
    'Version des Meta-Decision-Kernels (z. B. mdk-v1).';

COMMENT ON COLUMN app.signals_v1.meta_decision_bundle_json IS
    'Strukturierte Kernel-Artefakte: Abstinenz-Codes, EU-Proxy, Inputs — UI/Learning/Audit.';

COMMENT ON COLUMN app.signals_v1.operator_override_audit_json IS
    'Nur durch separaten Operator-Endpunkt: auditierte Freigabe; Engine setzt NULL.';

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_meta_decision_action
    ON app.signals_v1 (analysis_ts_ms DESC, meta_decision_action);
