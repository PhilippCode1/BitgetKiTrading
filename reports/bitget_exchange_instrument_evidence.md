# Bitget Exchange Instrument Evidence Report

Status: synthetischer Fail-closed-Nachweis fuer Bitget-Readiness, Key-Permissions und Instrumentenkatalog.

## Summary

- Datum/Zeit: `2026-04-25T23:27:31Z`
- Git SHA: `84d7b66`
- Private-Live-Entscheidung: `NO_GO`
- Full-Autonomous-Live: `NO_GO`
- Dry-run Ergebnis: `PASS_WITH_WARNINGS`
- Live-Write erlaubt: `false`
- Key-Permission-Evidence: `FAIL`
- Externe Exchange/Instrument-Evidence: `FAIL`
- Live-faehige Fixture-Assets: `0`
- Fehlende Instrument-Blockgruende: `0`
- Fehlende Asset-Universe-Blockgruende: `0`
- Fehlende Live-Preflight-Gruende: `0`

## Instrument-Fail-Closed-Coverage

- Abgedeckt: `missing_data_quality_gate`, `missing_liquidity_gate`, `missing_margin_coin_for_futures`, `missing_min_notional`, `missing_min_qty`, `missing_owner_approval`, `missing_precision`, `missing_product_type_for_futures`, `missing_risk_tier_gate`, `missing_strategy_evidence_gate`, `status_delisted`, `status_suspended`, `status_unknown`, `tier_0_blocked`, `tier_1_requires_live_candidate_status`, `tier_4_shadow_only`, `tier_5_blocked`
- Fehlend: -

- `unknown_status`: live_allowed=`False`, Gruende=status_unknown, tier_1_requires_live_candidate_status
- `delisted_status`: live_allowed=`False`, Gruende=status_delisted, tier_1_requires_live_candidate_status
- `suspended_status`: live_allowed=`False`, Gruende=status_suspended, tier_1_requires_live_candidate_status
- `missing_futures_product_type`: live_allowed=`False`, Gruende=missing_product_type_for_futures
- `missing_futures_margin_coin`: live_allowed=`False`, Gruende=missing_margin_coin_for_futures
- `missing_precision`: live_allowed=`False`, Gruende=missing_precision
- `missing_min_qty`: live_allowed=`False`, Gruende=missing_min_qty
- `missing_min_notional`: live_allowed=`False`, Gruende=missing_min_notional
- `missing_data_quality`: live_allowed=`False`, Gruende=missing_data_quality_gate
- `missing_liquidity`: live_allowed=`False`, Gruende=missing_liquidity_gate
- `missing_risk_tier`: live_allowed=`False`, Gruende=missing_risk_tier_gate
- `missing_strategy_evidence`: live_allowed=`False`, Gruende=missing_strategy_evidence_gate
- `missing_owner_approval`: live_allowed=`False`, Gruende=missing_owner_approval
- `tier_0`: live_allowed=`False`, Gruende=tier_0_blocked
- `tier_4_shadow_only`: live_allowed=`False`, Gruende=tier_4_shadow_only
- `tier_5`: live_allowed=`False`, Gruende=tier_5_blocked
- `tier_1_active_not_candidate`: live_allowed=`False`, Gruende=tier_1_requires_live_candidate_status

## Asset-Universe-Fixture

- Blockgruende: `datenqualitaet_nicht_ok`, `exchange_status_suspended`, `futures_margin_coin_fehlt`, `futures_product_type_fehlt`, `lot_size_fehlt`, `neues_asset_nicht_automatisch_live`, `risk_tier_unbekannt`, `shadow_nicht_freigegeben`, `tick_size_fehlt`
- Live-faehige Fixture-Assets: -

## Externe Evidence

- Assessment: `FAIL`; Fehler=`external_status_nicht_verified`, `environment_fehlt`, `git_sha_fehlt`, `reviewed_at_fehlt`, `reviewed_by_fehlt`, `key_permissions_ip_allowlist_enabled_nicht_belegt`, `key_permissions_account_protection_enabled_nicht_belegt`, `key_permissions_evidence_reference_fehlt`, `readonly_discovery_public_time_checked_nicht_belegt`, `readonly_discovery_public_instruments_checked_nicht_belegt`, `readonly_discovery_private_readonly_checked_nicht_belegt`, `readonly_discovery_server_time_skew_unbelegt_oder_zu_hoch`, `readonly_discovery_report_uri_fehlt`, `instrument_metadata_asset_universe_checked_nicht_belegt`, `instrument_metadata_all_symbols_v2_format_nicht_belegt`, `instrument_metadata_product_type_margin_coin_checked_nicht_belegt`, `instrument_metadata_precision_tick_lot_min_qty_checked_nicht_belegt`, `instrument_metadata_unknown_or_delisted_assets_block_live_nicht_belegt`, `instrument_metadata_metadata_fresh_nicht_belegt`, `instrument_metadata_instrument_count_fehlt`, `instrument_metadata_report_uri_fehlt`, `safety_owner_signoff_fehlt`

## Erforderlich vor Private Live

- Bitget-Key-Permission-Review mit read/trade=true, withdrawal=false, IP-Allowlist und Account-Schutz.
- Read-only Bitget-Discovery-Run mit Server-Time, Public Instruments und Private Read-only Account ohne Write-Endpunkte.
- Instrument-Metadata-Report mit v2-Symbolen, ProductType, MarginCoin, Precision, Tick/Lot/MinQty und Frischefenster.
- Owner-Signoff fuer Asset-Universe und Instrumentenkatalog vor Private-Live-Candidate.

## Einordnung

- Dieser Report nutzt nur Dry-run-/Fixture-/Template-Daten und sendet keine Orders.
- Echte Bitget-Readiness bleibt external_required; private Live bleibt NO_GO.
