# Liquiditaet, Spread, Slippage und Ausfuehrbarkeit pro Asset

## Ziel

Ein Signal darf nur live ausgefuehrt werden, wenn das Asset real handelbar ist.
Spread, Orderbook-Tiefe und erwartete Slippage werden pro Asset fail-closed geprueft.

## Metriken pro Asset

- bid/ask vorhanden
- spread bps
- top-of-book age
- depth top 5 (optional top 10/20)
- VWAP buy slippage
- VWAP sell slippage
- insufficient depth
- stale orderbook
- liquidity tier
- empfohlene max order notional
- live block reason

## Liquidity-Tiers

- `TIER_1`: sehr liquide, enger Spread
- `TIER_2`: liquide, akzeptabler Spread
- `TIER_3`: mittlere Liquiditaet, nur kleine Groessen mit Owner-Freigabe
- `TIER_4`: schwache Liquiditaet, kein Live
- `TIER_5`: blockiert/quarantine/delisted/unknown

## Harte Regeln

1. Fehlendes Orderbook blockiert Live.
2. Stale Orderbook blockiert Live.
3. Leere Bids oder Asks blockieren Live.
4. Spread ueber Schwelle blockiert Live.
5. VWAP-Slippage ueber Schwelle blockiert Live.
6. Unzureichende Top-N-Tiefe blockiert Live.
7. Tier 4 und Tier 5 blockieren Live.
8. Tier 3 braucht explizite Owner-Kleingroessenfreigabe.
9. Ordergroesse darf empfohlene Maximalgroesse nicht ueberschreiten.
10. Blockgruende muessen deutsch darstellbar sein.

## Main Console Modul „Liquiditaet“

Pro Asset sichtbar:

- Spread
- Orderbook-Frische
- Slippage-Schaetzung
- Tier
- Live-Blocker
- empfohlene Maximalgroesse

## Skript/Reports

```bash
python scripts/liquidity_quality_report.py --dry-run
python scripts/liquidity_quality_report.py --input-json tests/fixtures/liquidity_quality_sample.json --output-md reports/liquidity_quality_sample.md --output-json reports/liquidity_quality_sample.json
```

## No-Go

Kein Live-Opening bei unklarer, staler oder unzureichender Liquiditaet.
