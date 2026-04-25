# Live-Mirror-Gate-Matrix (Prompt 09)

Ziel: Kein `opening order`-Submit ohne vollstaendige Live-Mirror-Kette.  
Scope: `services/live-broker/src/live_broker/execution/service.py` und `services/live-broker/src/live_broker/orders/service.py`.

| Gate | Quelle (ENV/DB/Runtime) | Erwartet | Blockierende Meldung/Reason | Testname | Gilt fuer |
| --- | --- | --- | --- | --- | --- |
| Runtime-Modus | ENV `EXECUTION_MODE` (`effective_mode`) | `live` fuer Live-Submit | `live_submit_disabled` (kein Live-Opening bei `EXECUTION_MODE!=live`) | `test_live_intent_blocked_when_execution_mode_not_live` | opening |
| Live-Trade-Schalter | ENV `LIVE_TRADE_ENABLE` | `true` | `live_trade_disabled` / `LIVE_TRADE_ENABLE=false` | `test_live_intent_blocks_when_live_trade_disabled` | opening, replace, cancel (Order-API Write-Pfad) |
| Live-Broker aktiv | ENV `LIVE_BROKER_ENABLED` | `true` | `LIVE_BROKER_ENABLED=false` | `test_emergency_flatten_bypasses_submit_gate_in_live_mode` (negativer Pfad in Service) | opening, replace, cancel, emergency |
| Candidate-for-live Lane | Runtime `signal_payload.meta_trade_lane` | `candidate_for_live` | `meta_trade_lane_not_live_candidate` | `test_evaluate_intent_live_blocks_when_meta_trade_lane_is_paper_only` | opening |
| Shadow-Match Divergenz-Gate | Runtime `assess_shadow_live_divergence` + ENV `REQUIRE_SHADOW_MATCH_BEFORE_LIVE` | `match_ok=true` bei aktivem Gate | `shadow_live_divergence_gate` | `test_evaluate_intent_shadow_live_gate_blocks_high_signal_divergence` | opening |
| Shadow-Latch-Read | Redis-Latch `shadow:match:{execution_id}` | `present` bei aktivem Gate | `shadow_match_latch_miss` / `shadow_match_latch_absent` / `shadow_match_redis_unavailable` | `test_paper_broker_outage_blocks_live_no_redis_shadow_match_latch`, `test_order_service_blocks_open_without_shadow_match_latch`, `test_get_shadow_unavailable_activates_latch_and_raises` | opening |
| Execution-Binding | ENV `LIVE_REQUIRE_EXECUTION_BINDING` + DB `live.execution_decisions` | `source_execution_decision_id` vorhanden, Decision `live_candidate_recorded`, Symbol passt | Validation-Fehler (Binding required / unknown decision / action mismatch) | `test_order_service_blocks_open_when_execution_binding_required` | opening |
| Operator-Release | ENV `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN` + DB `live.operator_release` | Release vorhanden | `operator_release_required` | `test_order_service_blocks_open_without_operator_release` | opening |
| Safety-Latch | DB `live.audit_trails` (Kategorie `safety_latch`) | nicht aktiv (ausser risiko-reduzierend) | `live_safety_latch_active` / `Safety latch aktiv` | `test_live_intent_blocked_when_safety_latch_armed`, `test_safety_latch_blocks_order_create_before_private_api` | opening; reduce-only erlaubt |
| Kill-Switch | DB `live.kill_switch_events` | kein passender aktiver Switch (ausser risiko-reduzierend) | `kill_switch` Klassifikation | `test_kill_switch_blocks_normal_orders_but_allows_reduce_only`, `test_trade_kill_switch_blocks_replace_across_replace_chain` | opening, replace; reduce-only kontrolliert erlaubt |
| Exchange-Health | Runtime Probe + ENV `LIVE_REQUIRE_EXCHANGE_HEALTH` | Public API erreichbar (wenn Gate aktiv) | `exchange_health_unavailable` | `NO_EVIDENCE_UNIT (Gate im Code, kein dedizierter Unit-Testname gefunden)` | opening |
| Commercial/Tenant-Gates | DB `app.tenant_modul_mate_gates` + ENV `LIVE_BROKER_REQUIRE_COMMERCIAL_GATES`/`MODUL_MATE_GATE_ENFORCEMENT` | Trading fuer Tenant erlaubt | `modul_mate_live_trading_not_permitted`, `no_active_commercial_contract`, ... | `test_modul_mate_live_blocked_for_demo_only_gates`, `test_modul_mate_live_blocked_without_tenant_contract_admin_complete` | opening, replace, cancel |
| 7x Approval | Runtime-Intent + ENV `RISK_REQUIRE_7X_APPROVAL` | bei Hebel 7: `approved_7x=true` | `missing_7x_approval` | `test_decision_blocks_leverage_7_without_approval_before_submit_gate` | opening |
| Start-Ramp Hebel-Cap | ENV `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE` (Startprofil) | Live-Opening-Hebel `<= cap` (typisch `<=7`) | `live_ramp_leverage_cap_exceeded` | `test_live_intent_blocks_when_start_ramp_leverage_cap_exceeded` | opening |
| Exchange-Truth / Stale-Data | Runtime Truth-Fn + ENV `LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH` | truth ok, kein Drift/Stale-Block | `exchange_drift_or_snapshot_unhealthy`, `no_fresh_exchange_truth_channel`, `live_safety_latch_active` | `test_live_blocked_when_truth_gate_on_and_drift_flagged`, `test_live_blocked_when_no_fresh_truth_channel` | opening |
| Reduce-only Ausnahme | Request-Feld `reduce_only=true` + Risk-Policy `RISK_FORCE_REDUCE_ONLY_ON_ALERT` | Risikoabbau darf durch | kein Block bei Kill-Switch/Safety-Latch fuer reduce-only | `test_kill_switch_blocks_normal_orders_but_allows_reduce_only`, `test_safety_latch_blocks_create_order_allows_reduce_only` | reduce-only |
| Emergency-Flatten Ausnahme | API `emergency_flatten` + Kill-Switch-Feature | kontrolliert erlaubt in Live fuer Risikoabbau | nur Service-Guards (z. B. `EXECUTION_MODE!=live`) | `test_emergency_flatten_bypasses_submit_gate_in_live_mode` | emergency |

## Maschinenpruefung

- Script: `python scripts/verify_live_mirror_gate.py --env-file .env.production.example --dry-run --strict`
- Erwartung bei Template (`EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false`): `NOT_READY` (kein false PASS).
- Erwartung bei Fake-/Demo-/Local-Markern in Production-Werten: `FAIL`.
