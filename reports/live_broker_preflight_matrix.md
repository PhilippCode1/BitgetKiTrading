# Live-Broker Preflight Matrix

Status: synthetischer, repo-lokaler Fail-closed-Nachweis ohne echte Orders und ohne Secrets.

## Summary

- OK: `true`
- Szenarien: `24`
- Fehler: `0`

## Szenarien

| Szenario | Erwartung | Submit erlaubt | Blockgruende | Deutsche Operator-Gruende |
| --- | --- | --- | --- | --- |
| `execution_mode_not_live` | `block` | `nein` | `execution_mode_not_live` | Ausfuehrungsmodus ist nicht live. |
| `live_trade_enable_false` | `block` | `nein` | `live_trade_enable_false` | LIVE_TRADE_ENABLE ist nicht aktiv. |
| `owner_approval_missing` | `block` | `nein` | `owner_approval_missing` | Owner-Freigabe von Philipp fehlt. |
| `asset_not_in_catalog` | `block` | `nein` | `asset_not_in_catalog` | Asset ist nicht im Katalog vorhanden. |
| `asset_status_not_ok` | `block` | `nein` | `asset_status_not_ok` | Asset ist delisted, suspended oder unknown. |
| `asset_not_live_allowed` | `block` | `nein` | `asset_not_live_allowed` | Asset ist nicht live freigegeben. |
| `instrument_contract_missing` | `block` | `nein` | `instrument_contract_missing` | Instrument-Order-Contract ist unvollstaendig. |
| `instrument_metadata_stale` | `block` | `nein` | `instrument_metadata_stale` | Instrument-Metadaten sind stale. |
| `data_quality_not_pass` | `block` | `nein` | `data_quality_not_pass` | Datenqualitaet ist nicht livefaehig. |
| `liquidity_not_pass` | `block` | `nein` | `liquidity_not_pass` | Liquiditaet ist nicht ausreichend. |
| `slippage_too_high` | `block` | `nein` | `slippage_too_high` | Slippage liegt ueber der Schwelle. |
| `risk_tier_not_live_allowed` | `block` | `nein` | `risk_tier_not_live_allowed` | Risk-Tier erlaubt kein Live-Opening. |
| `order_sizing_not_safe` | `block` | `nein` | `order_sizing_not_safe` | Order-Sizing ist nicht sicher. |
| `portfolio_risk_not_safe` | `block` | `nein` | `portfolio_risk_not_safe` | Portfolio-Risk ist nicht sicher. |
| `strategy_evidence_missing_or_invalid` | `block` | `nein` | `strategy_evidence_missing_or_invalid` | Strategie-Evidence fehlt oder passt nicht. |
| `bitget_readiness_not_ok` | `block` | `nein` | `bitget_readiness_not_ok` | Bitget-Readiness ist nicht OK. |
| `reconcile_not_ok` | `block` | `nein` | `reconcile_not_ok` | Reconcile ist nicht OK. |
| `kill_switch_active` | `block` | `nein` | `kill_switch_active` | Kill-Switch ist aktiv. |
| `safety_latch_active` | `block` | `nein` | `safety_latch_active` | Safety-Latch ist aktiv. |
| `unknown_order_state_active` | `block` | `nein` | `unknown_order_state_active` | Unklarer Order-State ist aktiv. |
| `account_snapshot_stale` | `block` | `nein` | `account_snapshot_stale` | Account-Snapshot ist stale oder fehlt. |
| `idempotency_key_missing` | `block` | `nein` | `idempotency_key_missing` | Idempotency-Key fehlt. |
| `audit_context_missing` | `block` | `nein` | `audit_context_missing` | Audit-Context fehlt. |
| `all_green_control` | `allow` | `ja` | - | Preflight erfolgreich: alle Pflicht-Gates sind gruen. |

## Bewertung

- Alle synthetischen Pflichtgate-Szenarien blockieren fail-closed; der Kontrollfall bleibt submit-fahig.
- Dieser Report ersetzt keine externe Shadow-, Bitget-, Restore- oder Owner-Evidence.
