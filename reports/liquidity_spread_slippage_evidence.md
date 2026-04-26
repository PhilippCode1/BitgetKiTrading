# Liquidity Spread Slippage Evidence

- checked_at: `2026-04-26T09:28:04.007753+00:00`
- git_sha: `339dd15`
- assets_checked: `2`
- live_allowed_count: `0`
- status: `not_enough_evidence`
- decision: `not_enough_evidence`
- evidence_level: `synthetic`

## Assets

| Asset | Status | Spread bps | Slippage bps | Depth Score | Staleness ms | Live erlaubt | Gruende |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| BTCUSDT | `fail` | `0.15872889897699224` | `0.0` | `1.0` | `1500` | `False` | `lot_size_missing, market_order_slippage_missing, min_notional_missing, min_qty_missing, precision_missing, slippage_zu_hoch, tick_size_missing` |
| ALTUSDT | `fail` | `None` | `None` | `1.0` | `60000` | `False` | `depth_unzureichend, liquiditaetstier_blockiert_live, lot_size_missing, market_order_slippage_missing, min_notional_missing, min_qty_missing, orderbook_fehlt, orderbook_stale, ordergroesse_ueber_liquiditaetsgrenze, precision_missing, slippage_unbekannt, spread_unbekannt, tick_size_missing` |

## Einordnung

- Ohne echte Runtime-Orderbookdaten bleibt die Entscheidung `not_enough_evidence`.
- Synthetic/Test-Orderbooks sind kein Verified-Nachweis.
