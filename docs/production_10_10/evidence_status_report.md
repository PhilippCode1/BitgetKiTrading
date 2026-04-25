# Evidence Status Report

Status: automatisch erzeugt aus `docs/production_10_10/evidence_matrix.yaml`.

## Summary

- Kategorien: 30
- Live-Blocker nicht verified: 29
- Schema-Fehler: 0
- Warnungen: 29

## Status Counts

| Status | Anzahl |
| --- | ---: |
| `external_required` | 4 |
| `implemented` | 4 |
| `missing` | 0 |
| `partial` | 21 |
| `verified` | 1 |

## Live-Blocker

| ID | Titel | Status | Severity | Naechste Aktion |
| --- | --- | --- | --- | --- |
| main_console_information_architecture | Main Console Information Architecture | `implemented` | P1 | Dashboard-Routen inventarisieren und Main-Console-Konsolidierungsplan erzeugen. |
| german_only_ui | German-only UI | `partial` | P1 | UI-Textscanner und deutsche Main-Console-Copy-Review ergaenzen. |
| bitget_asset_universe | Bitget Asset Universe | `implemented` | P0 | Asset-Freigabe und Tests pro Asset-Familie mit Evidence verknuepfen. |
| instrument_catalog | Instrument Catalog | `implemented` | P0 | Katalogfrische und Exchange-Abgleich als Release-Evidence ablegen. |
| asset_quarantine_and_delisting | Asset Quarantine and Delisting | `partial` | P0 | Asset-Quarantine-Modell und Fail-closed-Tests ergaenzen. |
| market_data_quality_per_asset | Market Data Quality per Asset | `partial` | P0 | Per-Asset-Datenqualitaetsmatrix und Tests an Live-Broker-Gates koppeln. |
| liquidity_spread_slippage_per_asset | Liquidity, Spread and Slippage per Asset | `partial` | P0 | Liquiditaetsgate pro Asset-Klasse maschinenlesbar machen. |
| asset_risk_tiers | Asset Risk Tiers | `partial` | P0 | Asset-Risk-Tier-Datei und Validator erstellen. |
| multi_asset_order_sizing | Multi-Asset Order Sizing | `partial` | P0 | Multi-Asset-Sizing-Evidence pro Asset-Klasse ergaenzen. |
| portfolio_risk | Portfolio Risk | `partial` | P0 | Owner-Limits und aktuelle Test-Evidence fuer Portfolio-Risk archivieren. |
| strategy_validation_per_asset_class | Strategy Validation per Asset Class | `partial` | P0 | Asset-Klassen-Validierungsberichte erzeugen und verlinken. |
| live_broker_fail_closed | Live Broker Fail-Closed | `implemented` | P0 | Aktuelle Gate-Test-Evidence mit dieser Matrix verknuepfen. |
| order_idempotency | Order Idempotency | `partial` | P0 | Order-Idempotency-Report und Tests explizit referenzieren. |
| reconcile_safety | Reconcile Safety | `partial` | P0 | Reconcile-Divergenz-Evidence und Runbook konsolidieren. |
| kill_switch_safety_latch | Kill Switch and Safety Latch | `partial` | P0 | Drill-Evidence fuer Kill-Switch und Safety-Latch archivieren. |
| emergency_flatten | Emergency Flatten | `external_required` | P0 | Emergency-Flatten-Drill mit Git-SHA, Umgebung und PASS erzeugen. |
| bitget_exchange_readiness | Bitget Exchange Readiness | `external_required` | P0 | Read-only-/Demo-Abnahme und Key-Permission-Evidence extern archivieren. |
| env_secrets_profiles | ENV and Secrets Profiles | `partial` | P0 | Runtime-Secret-Store- und Rotation-Evidence extern nachweisen. |
| observability_slos | Observability and SLOs | `partial` | P1 | SLOs mit Main-Console-Go/No-Go und Alert-Drill verknuepfen. |
| alert_routing | Alert Routing | `partial` | P1 | Realen Alert-Drill ohne Secret-Leak archivieren. |
| backup_restore | Backup and Restore | `partial` | P0 | Staging-Restore mit RTO/RPO und PASS erzeugen. |
| shadow_burn_in | Shadow Burn-in | `external_required` | P0 | Realen Shadow-Burn-in-Bericht mit PASS und SHA256 ablegen. |
| disaster_recovery | Disaster Recovery | `partial` | P0 | End-to-end DR-Drill fuer Live-relevante States dokumentieren. |
| audit_forensics | Audit and Forensics | `partial` | P0 | Audit-/Forensics-Evidence pro Order-Lifecycle verlinken. |
| frontend_main_console_security | Frontend Main Console Security | `partial` | P0 | Main-Console-Security-Testplan ohne Customer-Verkaufsfokus erstellen. |
| admin_access_single_owner | Admin Access Single Owner | `partial` | P0 | Single-Owner-Admin-Policy und Tests aus Legacy-Rollenmodell ableiten. |
| deployment_parity | Deployment Parity | `partial` | P1 | Staging-/Production-Paritaetsreport fuer private Main Console erzeugen. |
| supply_chain_security | Supply Chain Security | `partial` | P1 | Aktuelle Supply-Chain-Audit-Evidence fuer Release ablegen. |
| final_go_no_go_scorecard | Final Go/No-Go Scorecard | `external_required` | P0 | Alle nicht verifizierten Live-Blocker schliessen und Owner-Go/No-Go dokumentieren. |

## Kategorien

| ID | Status | Blockiert Live | Evidence-Dateien |
| --- | --- | --- | --- |
| private_owner_scope | `verified` | nein | `AGENTS.md`, `docs/production_10_10/private_owner_scope.md`, `docs/production_10_10/README.md` |
| main_console_information_architecture | `implemented` | ja | `docs/production_10_10/main_console_product_direction.md`, `docs/production_10_10/main_console_bff_api_wiring.md`, `docs/dashboard_pages.md`, `docs/dashboard_operator.md`, `tools/check_main_console_wiring.py`, `tests/tools/test_check_main_console_wiring.py` |
| german_only_ui | `partial` | ja | `docs/production_10_10/main_console_product_direction.md`, `docs/dashboard_operator.md` |
| bitget_asset_universe | `implemented` | ja | `README.md`, `docs/bitget-config.md`, `docs/production_10_10/bitget_asset_universe.md`, `shared/python/src/shared_py/bitget/instruments.py`, `tools/check_bitget_asset_universe.py`, `tests/tools/test_check_bitget_asset_universe.py`, `tests/security/test_bitget_asset_universe_contracts.py` |
| instrument_catalog | `implemented` | ja | `docs/bitget-config.md`, `shared/python/src/shared_py/bitget/instruments.py` |
| asset_quarantine_and_delisting | `partial` | ja | `docs/bitget-config.md`, `docs/production_10_10/no_go_rules.md` |
| market_data_quality_per_asset | `partial` | ja | `docs/production_10_10/market_data_quality_per_asset.md`, `shared/python/src/shared_py/market_data_quality.py`, `scripts/asset_data_quality_report.py`, `tools/check_market_data_quality.py`, `tests/data/test_market_data_quality_contracts.py`, `tests/security/test_market_data_quality_live_blocking.py`, `tests/scripts/test_asset_data_quality_report.py`, `tests/tools/test_check_market_data_quality.py` |
| liquidity_spread_slippage_per_asset | `partial` | ja | `README.md`, `docs/risk_governor.md`, `docs/portfolio_risk_governor.md` |
| asset_risk_tiers | `partial` | ja | `docs/risk_governor.md`, `docs/portfolio_risk_governor.md` |
| multi_asset_order_sizing | `partial` | ja | `docs/risk_governor.md`, `docs/live_broker.md` |
| portfolio_risk | `partial` | ja | `docs/portfolio_risk_governor.md`, `docs/risk_governor.md` |
| strategy_validation_per_asset_class | `partial` | ja | `docs/model_stack_v2.md`, `docs/shadow_burn_in_ramp.md` |
| live_broker_fail_closed | `implemented` | ja | `docs/live_broker.md`, `docs/production_10_10/09_live_mirror_gate_matrix.md`, `docs/production_10_10/no_go_rules.md` |
| order_idempotency | `partial` | ja | `docs/live_broker.md`, `docs/production_10_10/no_go_rules.md`, `docs/production_10_10/live_safety_drill.md`, `scripts/live_safety_drill.py`, `tests/scripts/test_live_safety_drill.py` |
| reconcile_safety | `partial` | ja | `docs/live_broker.md`, `docs/production_10_10/no_go_rules.md` |
| kill_switch_safety_latch | `partial` | ja | `docs/live_broker.md`, `docs/production_10_10/no_go_rules.md` |
| emergency_flatten | `external_required` | ja | `docs/production_10_10/no_go_rules.md`, `docs/LaunchChecklist.md`, `docs/production_10_10/live_safety_drill.md`, `scripts/live_safety_drill.py`, `tests/scripts/test_live_safety_drill.py` |
| bitget_exchange_readiness | `external_required` | ja | `docs/bitget-config.md`, `docs/production_10_10/bitget_exchange_readiness.md`, `scripts/bitget_readiness_check.py`, `tools/check_bitget_exchange_readiness.py`, `tools/verify_bitget_rest.py`, `tests/scripts/test_bitget_readiness_check.py`, `tests/security/test_bitget_exchange_readiness_contracts.py`, `tests/tools/test_check_bitget_exchange_readiness.py` |
| env_secrets_profiles | `partial` | ja | `docs/SECRETS_MATRIX.md`, `docs/production_10_10/env_secrets_single_owner_safety.md`, `docs/env_profiles.md`, `tools/check_env_single_owner_safety.py`, `tools/validate_env_profile.py`, `tools/inventory_secret_surfaces.py`, `tests/tools/test_check_env_single_owner_safety.py`, `tests/security/test_env_single_owner_safety.py` |
| observability_slos | `partial` | ja | `docs/observability.md`, `OBSERVABILITY_AND_SLOS.md` |
| alert_routing | `partial` | ja | `docs/production_10_10/05_alert_routing_and_incident_drill.md`, `tools/verify_alert_routing.py` |
| backup_restore | `partial` | ja | `docs/recovery_runbook.md`, `docs/production_10_10/03_postgres_restore_drill.md`, `docs/production_10_10/disaster_recovery_restore_test.md`, `scripts/dr_postgres_restore_test.py`, `tools/dr_postgres_restore_drill.py`, `tests/scripts/test_dr_postgres_restore_test.py` |
| shadow_burn_in | `external_required` | ja | `docs/shadow_burn_in_ramp.md`, `docs/production_10_10/04_shadow_burn_in_certificate.md`, `docs/production_10_10/shadow_burn_in_certificate.md`, `scripts/verify_shadow_burn_in.py`, `tests/fixtures/shadow_burn_in_sample.json`, `tests/scripts/test_verify_shadow_burn_in.py` |
| disaster_recovery | `partial` | ja | `docs/recovery_runbook.md`, `docs/production_10_10/03_postgres_restore_drill.md`, `docs/production_10_10/disaster_recovery_restore_test.md`, `docs/production_10_10/live_safety_drill.md`, `scripts/live_safety_drill.py`, `tests/scripts/test_live_safety_drill.py` |
| audit_forensics | `partial` | ja | `docs/production_10_10/audit_forensics_replay_private_console.md`, `docs/dashboard_operator_console.md`, `shared/python/src/shared_py/audit_contracts.py`, `shared/python/src/shared_py/replay_summary.py`, `tools/check_private_audit_forensics.py`, `tests/tools/test_check_private_audit_forensics.py`, `tests/security/test_private_audit_forensics_contracts.py` |
| frontend_main_console_security | `partial` | ja | `docs/api_gateway_security.md`, `docs/dashboard_operator.md`, `docs/production_10_10/main_console_product_direction.md` |
| admin_access_single_owner | `partial` | ja | `docs/operator_urls_and_secrets.md`, `docs/api_gateway_security.md`, `docs/production_10_10/private_owner_scope.md` |
| deployment_parity | `partial` | ja | `docs/Deploy.md`, `docs/compose_runtime.md`, `docs/ci_release_gates.md` |
| supply_chain_security | `partial` | ja | `docs/REPO_SBOM_AND_RELEASE_METADATA.md`, `tools/pip_audit_supply_chain_gate.py`, `docs/ci_release_gates.md` |
| final_go_no_go_scorecard | `external_required` | ja | `docs/production_10_10/evidence_matrix.yaml`, `docs/production_10_10/no_go_rules.md`, `docs/production_10_10/production_readiness_scorecard.md`, `docs/production_10_10/production_readiness_scorecard_template.md`, `shared/python/src/shared_py/readiness_scorecard.py`, `scripts/production_readiness_scorecard.py`, `tests/scripts/test_production_readiness_scorecard.py`, `tests/security/test_readiness_scorecard_decisions.py`, `tools/check_10_10_evidence.py` |

## Issues

- WARNING `live_blocker_not_verified` `main_console_information_architecture`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `german_only_ui`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `bitget_asset_universe`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `instrument_catalog`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `asset_quarantine_and_delisting`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `market_data_quality_per_asset`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `liquidity_spread_slippage_per_asset`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `asset_risk_tiers`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `multi_asset_order_sizing`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `portfolio_risk`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `strategy_validation_per_asset_class`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `live_broker_fail_closed`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `order_idempotency`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `reconcile_safety`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `kill_switch_safety_latch`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `emergency_flatten`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `bitget_exchange_readiness`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `env_secrets_profiles`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `observability_slos`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `alert_routing`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `backup_restore`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `shadow_burn_in`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `disaster_recovery`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `audit_forensics`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `frontend_main_console_security`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `admin_access_single_owner`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `deployment_parity`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `supply_chain_security`: blocks live trading and is not verified
- WARNING `live_blocker_not_verified` `final_go_no_go_scorecard`: blocks live trading and is not verified
