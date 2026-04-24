-- DoD: Nach automatischer Befoerderung (Challenger-Backtest-Gate + assign champion)
-- liefert promotion_gate_report.champion_challenger_backtest.status = 'PROMOTED'
-- und verweist optional auf die Audit-Zeile app.audit_log (action = champion_assigned).
--
-- Erwartung: mindestens eine Zeile mit status PROMOTED und Begruendung im JSONB.

SELECT
  h.history_id,
  h.model_name,
  h.run_id,
  h.started_at,
  h.changed_by,
  h.promotion_gate_report->'champion_challenger_backtest'->>'status' AS champion_challenger_status,
  h.promotion_gate_report->'champion_challenger_backtest'->'decision' AS promotion_decision,
  h.promotion_gate_report->'champion_challenger_backtest'->'n_simulated_trades' AS n_simulated_trades,
  a.entity_id,
  a.action,
  a.payload->'promotion_gate_report'->'champion_challenger_backtest'->>'status' AS audit_report_status
FROM app.model_champion_history h
LEFT JOIN LATERAL (
  SELECT entity_id, action, payload, created_ts
  FROM app.audit_log
  WHERE entity_table = 'model_registry_v2'
    AND action = 'champion_assigned'
    AND (payload->>'run_id') = h.run_id::text
  ORDER BY created_ts DESC
  LIMIT 1
) a ON true
WHERE h.ended_at IS NULL
  AND h.promotion_gate_report->'champion_challenger_backtest'->>'status' = 'PROMOTED'
ORDER BY h.started_at DESC
LIMIT 20;
