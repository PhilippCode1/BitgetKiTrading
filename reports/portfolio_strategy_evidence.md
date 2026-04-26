# Portfolio Strategy Evidence Report

Status: synthetischer Fail-closed-Nachweis fuer Portfolio-Risk und Strategy-Validation pro Asset-Klasse.

## Summary

- Datum/Zeit: `2026-04-26T09:48:27Z`
- Git SHA: `339dd15`
- Private-Live-Entscheidung: `NO_GO`
- Full-Autonomous-Live: `NO_GO`
- Externe Evidence: `FAIL`
- Fehlende Portfolio-Blockgruende: `0`
- Fehlende Strategy-Blockgruende: `0`
- Fehlende Multi-Asset-Strategy-Gruende: `0`
- Fehlende Live-Preflight-Gruende: `0`

## Portfolio-Risk-Coverage

- Abgedeckt: `account_equity_ungueltig`, `correlation_stress_zu_hoch`, `family_exposure_zu_hoch`, `funding_konzentration_zu_hoch`, `largest_position_risk_ueber_limit`, `margin_usage_ueber_limit`, `max_concurrent_positions_ueberschritten`, `net_long_exposure_ueber_limit`, `net_short_exposure_ueber_limit`, `owner_limits_fehlen`, `portfolio_snapshot_fehlt`, `portfolio_snapshot_stale`, `total_exposure_ueber_limit`, `zu_viele_pending_live_candidates`, `zu_viele_pending_orders`
- Fehlend: -

- `missing_snapshot`: blockiert=`True`, Gruende=portfolio_snapshot_fehlt
- `stale_snapshot`: blockiert=`True`, Gruende=portfolio_snapshot_stale, owner_limits_fehlen
- `invalid_equity`: blockiert=`True`, Gruende=account_equity_ungueltig, margin_usage_ueber_limit, owner_limits_fehlen
- `total_exposure_over_limit`: blockiert=`True`, Gruende=total_exposure_ueber_limit, net_long_exposure_ueber_limit, family_exposure_zu_hoch, owner_limits_fehlen
- `margin_usage_over_limit`: blockiert=`True`, Gruende=margin_usage_ueber_limit, owner_limits_fehlen
- `largest_position_risk_over_limit`: blockiert=`True`, Gruende=largest_position_risk_ueber_limit, owner_limits_fehlen
- `max_concurrent_positions`: blockiert=`True`, Gruende=max_concurrent_positions_ueberschritten, owner_limits_fehlen
- `pending_orders_over_limit`: blockiert=`True`, Gruende=zu_viele_pending_orders, owner_limits_fehlen
- `pending_live_candidates_over_limit`: blockiert=`True`, Gruende=zu_viele_pending_live_candidates, owner_limits_fehlen
- `net_long_exposure_over_limit`: blockiert=`True`, Gruende=net_long_exposure_ueber_limit, owner_limits_fehlen
- `net_short_exposure_over_limit`: blockiert=`True`, Gruende=net_short_exposure_ueber_limit, owner_limits_fehlen
- `correlation_stress_over_limit`: blockiert=`True`, Gruende=correlation_stress_zu_hoch, owner_limits_fehlen
- `funding_concentration_over_limit`: blockiert=`True`, Gruende=funding_konzentration_zu_hoch, owner_limits_fehlen
- `family_exposure_over_limit`: blockiert=`True`, Gruende=net_long_exposure_ueber_limit, family_exposure_zu_hoch, owner_limits_fehlen

## Strategy-Asset-Evidence

- `trend_follow_v2`/`BTCUSDT`: blockiert=`True`, Gruende=fees_fehlen, spread_fehlt, slippage_fehlt, funding_fehlt_futures, drawdown_fehlt, zu_wenige_trades, profit_factor_fehlt, out_of_sample_fehlt_oder_nicht_bestanden, walk_forward_fehlt_oder_nicht_bestanden, paper_evidence_fehlt_oder_nicht_bestanden, shadow_evidence_fehlt_oder_nicht_bestanden, marktphasen_nicht_ausreichend, verlustserie_nicht_bewertet, risk_per_trade_unbekannt, parameter_hash_fehlt, parameter_nicht_reproduzierbar, checked_at_fehlt, git_sha_fehlt
- `trend_follow_v2`/`ALTUSDT`: blockiert=`True`, Gruende=asset_class_unknown, strategy_evidence_expired, risk_tier_mismatch, data_quality_mismatch, strategy_scope_mismatch, fees_fehlen, spread_fehlt, slippage_fehlt, funding_fehlt_futures, drawdown_fehlt, zu_wenige_trades, profit_factor_fehlt, out_of_sample_fehlt_oder_nicht_bestanden, walk_forward_fehlt_oder_nicht_bestanden, paper_evidence_fehlt_oder_nicht_bestanden, shadow_evidence_fehlt_oder_nicht_bestanden, marktphasen_nicht_ausreichend, verlustserie_nicht_bewertet, risk_per_trade_unbekannt, parameter_hash_fehlt, parameter_nicht_reproduzierbar, checked_at_fehlt, git_sha_fehlt
- `synthetic_research_only_guard`/`ETHUSDT`: blockiert=`True`, Gruende=evidence_status_nicht_live_faehig, fees_fehlen, spread_fehlt, slippage_fehlt, funding_fehlt_futures, drawdown_fehlt, zu_wenige_trades, profit_factor_fehlt, out_of_sample_fehlt_oder_nicht_bestanden, walk_forward_fehlt_oder_nicht_bestanden, paper_evidence_fehlt_oder_nicht_bestanden, shadow_evidence_fehlt_oder_nicht_bestanden, marktphasen_nicht_ausreichend, verlustserie_nicht_bewertet, risk_per_trade_unbekannt, parameter_hash_fehlt, parameter_nicht_reproduzierbar, checked_at_fehlt, git_sha_fehlt

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
