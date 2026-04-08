-- Erweitert alert.alert_outbox.alert_type um produktiv genutzte Typen (Policies + Operator-Intel).

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
            'OPERATOR_EXECUTION_UPDATE'
        )
    );
