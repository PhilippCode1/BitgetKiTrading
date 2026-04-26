# Asset Preflight Evidence Report

Status: kombinierte repo-lokale Fixture-Evidence fuer Asset Governance, Datenqualitaet, Liquiditaet und Risk-Tiers.

## Summary

- Datum/Zeit: `2026-04-25T23:07:35.748385+00:00`
- Git SHA: `84d7b66`
- Gepruefte Assets: `2`
- Live technisch blockiert: `2`
- Live technisch erlaubt: `0`
- Private-Live-Entscheidung: `NO_GO`
- Abgedeckte Live-Preflight-Blockgruende: `9`
- Fehlende Required-Preflight-Blockgruende: `0`

## Assets

| Asset | Governance | Data Quality | Liquidity | Risk Tier | Sizing | Status | Blockgruende |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALTUSDT | `quarantine` | `data_live_blocked` | `TIER_5` | `RISK_TIER_UNKNOWN` | `blocked` | `LIVE_BLOCKED` | `state_quarantine_nicht_live_freigegeben`, `datenqualitaet_nicht_ok`, `liquiditaet_nicht_ok`, `strategy_evidence_nicht_ok`, `bitget_status_nicht_klar`, `candle_critical_gap`, `orderbook_stale`, `top_of_book_missing`, `funding_missing`, `open_interest_missing`, `orderbook_fehlt`, `spread_unbekannt`, `slippage_unbekannt`, `depth_unzureichend`, `ordergroesse_ueber_liquiditaetsgrenze`, `liquiditaetstier_blockiert_live`, `asset_tier_unknown`, `asset_tier_missing_or_unknown`, `owner_approval_missing`, `asset_status_not_ok`, `asset_not_live_allowed`, `data_quality_not_pass`, `liquidity_not_pass`, `slippage_too_high`, `risk_tier_not_live_allowed`, `order_sizing_not_safe`, `strategy_evidence_missing_or_invalid` |
| BTCUSDT | `live_candidate` | `data_ok` | `TIER_1` | `RISK_TIER_1_MAJOR_LIQUID` | `valid` | `LIVE_BLOCKED` | `state_live_candidate_nicht_live_freigegeben`, `slippage_zu_hoch`, `liquidity_not_green`, `owner_approval_missing`, `asset_not_live_allowed`, `liquidity_not_pass`, `slippage_too_high` |

## Live-Broker-Preflight-Coverage

- Abgedeckt: `asset_not_live_allowed`, `asset_status_not_ok`, `data_quality_not_pass`, `liquidity_not_pass`, `order_sizing_not_safe`, `owner_approval_missing`, `risk_tier_not_live_allowed`, `slippage_too_high`, `strategy_evidence_missing_or_invalid`
- Fehlend: -

## Deutsche Risk-Hinweise

- `ALTUSDT`: Asset ALTUSDT: Tier=RISK_TIER_UNKNOWN (RISK_TIER_E), max Hebel=1x, max Notional=0.00 USDT, Grunde=asset_tier_unknown. Hinweis: Unbekannter Tier-Kontext, fail-closed blockiert.
  - Liquiditaet: Orderbook fehlt; Live-Ausfuehrung ist gesperrt.
  - Liquiditaet: Orderbook ist stale; Live-Ausfuehrung ist gesperrt.
  - Liquiditaet: Spread ist unbekannt; Live-Ausfuehrung ist gesperrt.
  - Liquiditaet: Slippage ist unbekannt; Live-Ausfuehrung ist gesperrt.
  - Liquiditaet: Top-N-Tiefe ist unzureichend fuer die geplante Ordergroesse.
  - Liquiditaet: Geplante Ordergroesse ueberschreitet die empfohlene Liquiditaetsgrenze.
  - Liquiditaet: Liquiditaets-Tier blockiert Live-Opening.
- `BTCUSDT`: Asset BTCUSDT: Tier=RISK_TIER_1_MAJOR_LIQUID (RISK_TIER_A), max Hebel=7x, max Notional=5000.00 USDT, Grunde=liquidity_not_green, owner_approval_missing. Hinweis: Sehr liquide Hauptklasse; konservative Live-Freigabe mit vollen Gates.
  - Liquiditaet: Erwartete VWAP-Slippage ist zu hoch.

## Einordnung

- Repo-lokale Fixture-Evidence; keine echte Bitget-/Shadow-/Owner-Evidence.
- LIVE_ALLOWED in diesem Report waere nur technisch vorpruefbar, nicht private_live_allowed.
- Fehlende Governance-, Datenqualitaets-, Liquiditaets- oder Risk-Tier-Evidence blockiert fail-closed.
- Live-Broker-Preflight-Codes werden als Schnittstelle mitbelegt; fehlende Required-Codes bleiben P0-Evidence-Gap.
