-- DoD (Prompt 49): historische War-Room-/Apex-Daten bilden die Basis fuer
-- learn.trade_evaluations angereichert mit Konsens -> consensus_penalty im naechsten Train-Run
-- (Join: signal_id = market_event_json.signal_id im Apex-Kanon, Migration 617).
--
-- Wenn belegt, zeigen Zeilen mit: Spezialisten-Disharmonie (hohe Unsicherheit) und Verlust.

SELECT
  te.evaluation_id,
  te.paper_trade_id,
  te.signal_id,
  te.symbol,
  te.pnl_net_usdt,
  te.decision_ts_ms,
  (e.canonical_payload_text::json
    ->'war_room'->>'consensus_status') AS war_room_consensus_status,
  (e.canonical_payload_text::json
    ->'war_room'->>'macro_quant_high_uncertainty')::boolean AS specialist_macro_quant_disagreement,
  CASE
    WHEN
      (e.canonical_payload_text::json->'war_room'->>'consensus_status') = 'high_uncertainty'
      OR (e.canonical_payload_text::json
        ->'war_room'->>'macro_quant_high_uncertainty')::boolean
    THEN
      CASE WHEN te.pnl_net_usdt < 0 THEN 1.0::double precision ELSE 0.0::double precision END
    ELSE
      0.0
  END AS hard_lesson_flag_like_consensus_penalty
FROM learn.trade_evaluations te
INNER JOIN LATERAL (
  SELECT
    a.id, a.canonical_payload_text, a.decision_id
  FROM app.apex_audit_ledger_entries a
  CROSS JOIN LATERAL (
    SELECT (a.canonical_payload_text::json->'market_event_json'->>'signal_id')::uuid AS sig
  ) x
  WHERE x.sig = te.signal_id
  ORDER BY a.id DESC
  LIMIT 1
) e ON true
WHERE te.take_trade_label IS NOT NULL
  AND te.signal_id IS NOT NULL
ORDER BY te.decision_ts_ms DESC
LIMIT 30;
