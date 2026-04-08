-- Stop-Budget-Policy: Audit- und Lernfelder (Ausfuehrbarkeit vs. Hebel-Kurve)

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS stop_distance_pct numeric,
    ADD COLUMN IF NOT EXISTS stop_budget_max_pct_allowed numeric,
    ADD COLUMN IF NOT EXISTS stop_min_executable_pct numeric,
    ADD COLUMN IF NOT EXISTS stop_to_spread_ratio numeric,
    ADD COLUMN IF NOT EXISTS stop_quality_0_1 numeric,
    ADD COLUMN IF NOT EXISTS stop_executability_0_1 numeric,
    ADD COLUMN IF NOT EXISTS stop_fragility_0_1 numeric,
    ADD COLUMN IF NOT EXISTS stop_budget_policy_version text;
