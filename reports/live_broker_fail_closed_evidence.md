# Live Broker Fail-Closed Evidence Report

- Generiert: `2026-04-26T09:54:30Z`
- Git SHA: `339dd15`
- Status: `implemented`
- Decision: `NOT_ENOUGH_EVIDENCE`
- Verified: `False`
- Evidence-Level: `synthetic`
- Preflight ok: `True`

- `db_unavailable`: expected=block actual=block pass=True reason=db_unavailable_blocks_submit
- `redis_unavailable`: expected=block actual=block pass=True reason=redis_unavailable_blocks_submit
- `risk_timeout`: expected=block actual=block pass=True reason=risk_timeout_blocks_submit
- `market_data_stale`: expected=block actual=block pass=True reason=market_data_stale_blocks_submit
- `orderbook_missing`: expected=block actual=block pass=True reason=orderbook_missing_blocks_submit
- `exchange_truth_missing`: expected=block actual=block pass=True reason=exchange_truth_missing_blocks_submit
- `unknown_instrument`: expected=block actual=block pass=True reason=unknown_instrument_blocks_submit
- `quarantined_asset`: expected=block actual=block pass=True reason=quarantined_asset_blocks_submit
- `shadow_mismatch`: expected=block actual=block pass=True reason=shadow_mismatch_blocks_submit
- `operator_release_missing`: expected=block actual=block pass=True reason=operator_release_missing_blocks_submit
- `safety_latch_active`: expected=block actual=block pass=True reason=safety_latch_active_blocks_submit
- `kill_switch_active`: expected=block actual=block pass=True reason=kill_switch_active_blocks_submit
- `global_halt_active`: expected=block actual=block pass=True reason=global_halt_active_blocks_submit
- `bitget_auth_error`: expected=block actual=block pass=True reason=bitget_auth_error_blocks_submit
- `bitget_permission_error`: expected=block actual=block pass=True reason=bitget_permission_error_blocks_submit
- `bitget_timeout`: expected=block actual=block pass=True reason=bitget_timeout_blocks_submit
- `bitget_5xx`: expected=block actual=block pass=True reason=bitget_5xx_blocks_submit
- `duplicate_client_oid`: expected=block actual=block pass=True reason=duplicate_client_oid_blocks_submit
- `reconcile_degraded`: expected=block actual=block pass=True reason=reconcile_degraded_blocks_submit
- `env_invalid`: expected=block actual=block pass=True reason=env_invalid_blocks_submit
