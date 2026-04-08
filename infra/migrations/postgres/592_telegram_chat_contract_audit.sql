-- Telegram/Chat-Vertrag v1: erweiterte Operator-Audit-Felder, neue Outcomes, neue OPERATOR_* Outbox-Typen.

ALTER TABLE alert.alert_outbox DROP CONSTRAINT IF EXISTS alert_outbox_alert_type_check;

ALTER TABLE alert.alert_outbox
    ADD CONSTRAINT alert_outbox_alert_type_check CHECK (
        alert_type IN (
            'GROSS_SIGNAL',
            'CORE_SIGNAL',
            'TREND_WARN',
            'TRADE_CLOSED',
            'STOP_DANGER',
            'NEWS_HIGH',
            'SYSTEM_ALERT',
            'LIVE_EXECUTION_POLICY_WARN',
            'LIVE_BROKER_KILL_SWITCH',
            'LIVE_BROKER_EMERGENCY_FLATTEN',
            'LIVE_BROKER_ORDER_TIMEOUT',
            'LIVE_BROKER_RECONCILE',
            'LIVE_BROKER_MONITOR',
            'OPERATOR_STRATEGY_INTENT',
            'OPERATOR_NO_TRADE',
            'OPERATOR_PLAN_SUMMARY',
            'OPERATOR_RISK_NOTICE',
            'OPERATOR_FILL',
            'OPERATOR_EXIT',
            'OPERATOR_POST_TRADE',
            'OPERATOR_EXECUTION_UPDATE',
            'OPERATOR_PRE_TRADE',
            'OPERATOR_RELEASE_PENDING',
            'OPERATOR_TRADE_OPEN',
            'OPERATOR_TRADE_CLOSE',
            'OPERATOR_INCIDENT',
            'OPERATOR_SAFETY_LATCH'
        )
    );

ALTER TABLE alert.operator_action_audit DROP CONSTRAINT IF EXISTS operator_action_audit_outcome_check;

ALTER TABLE alert.operator_action_audit
    ADD COLUMN IF NOT EXISTS chat_contract_version text NOT NULL DEFAULT 'telegram-chat-contract-v1',
    ADD COLUMN IF NOT EXISTS rbac_scope text NULL,
    ADD COLUMN IF NOT EXISTS manual_action_token_fp text NULL;

ALTER TABLE alert.operator_action_audit
    ADD CONSTRAINT operator_action_audit_outcome_check CHECK (outcome IN (
        'rejected_forbidden_command',
        'rejected_invalid_args',
        'rejected_not_enabled',
        'rejected_not_eligible',
        'rejected_expired',
        'rejected_bad_code',
        'rejected_wrong_chat',
        'rejected_http_error',
        'rejected_missing_upstream',
        'rejected_rbac',
        'rejected_manual_token',
        'pending_created',
        'pending_cancelled',
        'executed_ok',
        'executed_error'
    ));
