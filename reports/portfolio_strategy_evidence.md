# Portfolio Strategy Evidence Report

Status: synthetischer Fail-closed-Nachweis fuer Portfolio-Risk und Strategy-Validation pro Asset-Klasse.

## Summary

- Datum/Zeit: `2026-04-25T23:19:36Z`
- Git SHA: `84d7b66`
- Private-Live-Entscheidung: `NO_GO`
- Full-Autonomous-Live: `NO_GO`
- Externe Evidence: `FAIL`
- Fehlende Portfolio-Blockgruende: `0`
- Fehlende Strategy-Blockgruende: `0`
- Fehlende Multi-Asset-Strategy-Gruende: `0`
- Fehlende Live-Preflight-Gruende: `0`

## Portfolio-Risk-Coverage

- Abgedeckt: `account_equity_ungueltig`, `correlation_stress_zu_hoch`, `family_exposure_zu_hoch`, `funding_konzentration_zu_hoch`, `largest_position_risk_ueber_limit`, `margin_usage_ueber_limit`, `max_concurrent_positions_ueberschritten`, `net_long_exposure_ueber_limit`, `net_short_exposure_ueber_limit`, `portfolio_snapshot_fehlt`, `portfolio_snapshot_stale`, `total_exposure_ueber_limit`, `zu_viele_pending_live_candidates`, `zu_viele_pending_orders`
- Fehlend: -

- `missing_snapshot`: blockiert=`True`, Gruende=portfolio_snapshot_fehlt
- `stale_snapshot`: blockiert=`True`, Gruende=portfolio_snapshot_stale
- `invalid_equity`: blockiert=`True`, Gruende=account_equity_ungueltig, margin_usage_ueber_limit
- `total_exposure_over_limit`: blockiert=`True`, Gruende=total_exposure_ueber_limit, net_long_exposure_ueber_limit, family_exposure_zu_hoch
- `margin_usage_over_limit`: blockiert=`True`, Gruende=margin_usage_ueber_limit
- `largest_position_risk_over_limit`: blockiert=`True`, Gruende=largest_position_risk_ueber_limit
- `max_concurrent_positions`: blockiert=`True`, Gruende=max_concurrent_positions_ueberschritten
- `pending_orders_over_limit`: blockiert=`True`, Gruende=zu_viele_pending_orders
- `pending_live_candidates_over_limit`: blockiert=`True`, Gruende=zu_viele_pending_live_candidates
- `net_long_exposure_over_limit`: blockiert=`True`, Gruende=net_long_exposure_ueber_limit
- `net_short_exposure_over_limit`: blockiert=`True`, Gruende=net_short_exposure_ueber_limit
- `correlation_stress_over_limit`: blockiert=`True`, Gruende=correlation_stress_zu_hoch
- `funding_concentration_over_limit`: blockiert=`True`, Gruende=funding_konzentration_zu_hoch
- `family_exposure_over_limit`: blockiert=`True`, Gruende=net_long_exposure_ueber_limit, family_exposure_zu_hoch

## Strategy-Asset-Evidence

- `trend_follow_v2`/`BTCUSDT`: blockiert=`False`, Gruende=-
- `trend_follow_v2`/`ALTUSDT`: blockiert=`True`, Gruende=asset_class_unknown, strategy_evidence_expired, risk_tier_mismatch, data_quality_mismatch, strategy_scope_mismatch
- `synthetic_research_only_guard`/`ETHUSDT`: blockiert=`True`, Gruende=evidence_status_nicht_live_faehig

## Multi-Asset-Strategy-Evidence

- `strat_major_momentum`/`BTCUSDT`: verdict=`PASS`, Gruende=-
- `strat_new_listing_guard`/`NEWCOINUSDT`: verdict=`FAIL`, Gruende=Asset-Klasse ist für Live gesperrt/quarantänepflichtig., Walk-forward-Evidence fehlt., Slippage/Fees/Funding-Evidence fehlt., Out-of-sample-Evidence fehlt., Shadow-Burn-in-Evidence fehlt., Drawdown-Regel verletzt., Regime-Breakdown unzureichend., Asset-Klassen-Breakdown unzureichend., No-Trade-Qualität unzureichend., Datenqualität nicht ausreichend., Negative oder null Expectancy nach Kosten., Max-Drawdown über 20%., Extrem geringe Trade-Anzahl., Zu wenige Trades für robuste Aussage.

## Externe Evidence

- Assessment: `FAIL`; Fehler=`external_status_nicht_verified`, `evidence_environment_template`, `git_sha_template`, `owner_limits_signed_by_fehlt`, `owner_limits_signed_at_fehlt`, `owner_limits_max_total_notional_fehlt`, `owner_limits_max_margin_usage_fehlt`, `owner_limits_max_family_exposure_fehlt`, `owner_limits_max_net_directional_exposure_fehlt`, `owner_limits_max_correlation_stress_fehlt`, `owner_limits_document_uri_fehlt`, `portfolio_drill_runtime_snapshot_fresh_nicht_belegt`, `portfolio_drill_missing_snapshot_blocks_live_nicht_belegt`, `portfolio_drill_stale_snapshot_blocks_live_nicht_belegt`, `portfolio_drill_exposure_limit_blocks_live_nicht_belegt`, `portfolio_drill_correlation_unknown_blocks_live_nicht_belegt`, `portfolio_drill_family_exposure_blocks_live_nicht_belegt`, `portfolio_drill_pending_orders_counted_in_exposure_nicht_belegt`, `strategy_asset_classes_covered_fehlt`, `strategy_validation_backtest_reports_present_nicht_belegt`, `strategy_validation_walk_forward_reports_present_nicht_belegt`, `strategy_validation_paper_reports_present_nicht_belegt`, `strategy_validation_shadow_reports_present_nicht_belegt`, `strategy_validation_slippage_fees_funding_included_nicht_belegt`, `strategy_validation_drawdown_limits_passed_nicht_belegt`, `strategy_validation_no_trade_quality_checked_nicht_belegt`, `strategy_validation_lineage_documented_nicht_belegt`, `shadow_burn_in_nicht_passed`, `shadow_burn_in_real_shadow_period_started_at_fehlt`, `shadow_burn_in_real_shadow_period_ended_at_fehlt`, `shadow_burn_in_divergence_report_uri_fehlt`, `operator_approval_record_uri_template`

## Erforderlich vor Private Live

- Owner-signierte Portfolio-Limits mit Git-SHA und Umgebung.
- Staging-/Shadow-Portfolio-Drill mit fehlendem/stalem Snapshot, Exposure-, Korrelation- und Family-Limit.
- Backtest-, Walk-forward-, Paper-, Shadow- und Slippage/Funding-Reports pro Asset-Klasse.
- Shadow-Burn-in-Report mit Divergenz-Auswertung und Operator-/Owner-Freigabe.

## Einordnung

- Dieser Report erzeugt synthetische Repo-Evidence ohne echte Orders und ohne Secrets.
- Implementierte Gates sind nicht gleich verified; private Live bleibt bis externer Evidence NO_GO.
