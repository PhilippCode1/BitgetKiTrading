-- Prompt 26: Admin Rules Store (nicht-sensible Schwellen / Weightings)

CREATE TABLE IF NOT EXISTS app.admin_rules (
    rule_set_id text PRIMARY KEY,
    rules_json jsonb NOT NULL,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

INSERT INTO app.admin_rules (rule_set_id, rules_json)
VALUES (
    'default',
    '{
        "signal": {"min_strength_core": 60, "min_strength_gross": 80},
        "strategy": {"min_risk_score": 60, "max_positions": 1},
        "news": {"shock_score": 80, "cooldown_sec": 1800}
    }'::jsonb
)
ON CONFLICT (rule_set_id) DO NOTHING;
