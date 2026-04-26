# Asset Governance Evidence Report

Status: kombinierter repo-lokaler Nachweis fuer Asset-Quarantaene, Datenqualitaet, Liquiditaet, Risk-Tiers und Sizing.

## Summary

- Datum/Zeit: `2026-04-26T09:10:30.984789+00:00`
- Git SHA: `339dd15`
- Private Live: `NO_GO`
- Full Autonomous Live: `NO_GO`
- Failures: `0`
- External Required: `5`
- Gepruefte Assets: `2`
- Live blockiert: `2`
- Live erlaubt: `0`
- Fehlende Preflight-Pflichtgruende: `0`
- Fehlende Blockgrund-Pflichtabdeckung: `0`

## Assets

| Asset | Governance | Data Quality | Liquidity | Risk Tier | Sizing | Status |
| --- | --- | --- | --- | --- | --- | --- |
| ALTUSDT | `quarantine` | `data_live_blocked` | `TIER_5` | `RISK_TIER_UNKNOWN` | `blocked` | `LIVE_BLOCKED` |
| BTCUSDT | `live_candidate` | `data_ok` | `TIER_1` | `RISK_TIER_1_MAJOR_LIQUID` | `valid` | `LIVE_BLOCKED` |

## External Required

- `real_bitget_asset_universe_refresh_missing`
- `real_per_asset_market_data_quality_window_missing`
- `real_orderbook_liquidity_slippage_window_missing`
- `owner_signed_asset_risk_tier_acceptance_missing`
- `shadow_burn_in_per_asset_class_missing`

## Einordnung

- Dieser Report beweist repo-lokale Asset-Governance-Contracts und Fixture-Fail-Closed-Verhalten.
- Keine Fixture darf private Live freigeben; echte Bitget-/Shadow-/Owner-Evidence bleibt external_required.
- Quarantaene, stale Daten, schlechte Liquiditaet, unbekannte Risk-Tiers und unsicheres Sizing muessen vor Submit blockieren.
