-- Portfolio-/Konto-Stress vs. Live-Execution (risk-governor-v2).
-- Keine neuen Spalten: Felder liegen in source_snapshot_json.hybrid_decision.risk_governor
-- (live_execution_block_reasons_json, universal_hard_block_reasons_json, portfolio_risk_synthesis_json).

COMMENT ON COLUMN app.signals_v1.source_snapshot_json IS
    'Hybrid-Entscheidung inkl. risk_governor: universal_hard vs. live_execution_block (Echtgeld-Gate im Live-Broker).';
