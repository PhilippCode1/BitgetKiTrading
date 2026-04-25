# Multi-Asset Portfolio-Risiko

## Warum Einzeltrade-Risk nicht reicht

Mehrere einzeln gute Trades koennen gemeinsam gefaehrlich sein. Korrelation,
gleiche Richtung und Cluster koennen Gesamtverluste stark erhoehen.

## Bewertete Exposure-Arten

- total notional exposure
- margin usage
- largest position risk
- offene Positionen
- pending orders
- pending live candidates
- net long / net short exposure
- family exposure / cluster exposure
- correlation stress
- funding concentration
- basis risk
- gleiche Richtung / Duplicate-Exposure
- stale portfolio snapshot

## Harte Regeln

1. Fehlender oder stale Snapshot blockiert Live-Opening.
2. Exposure, Margin, Largest Position Risk, Concurrent Positions ueber Limit blockieren.
3. Pending Orders und Pending Live Candidates werden konservativ eingerechnet.
4. Correlation-Stress ueber Schwelle blockiert.
5. Unknown Correlation wird konservativ gecappt oder blockiert.
6. Deutsche Blockgruende sind Pflicht.
7. Portfolio-PASS bedeutet nur: naechster Gate-Schritt, nie Auto-Live.

## Main-Console Anzeige „Portfolio-Risiko“

- Gesamt-Exposure
- Margin Usage
- offene Positionen
- pending Orders
- pending Candidates
- Asset-Cluster/Familienexposure
- aktuelle Blockgruende
- Portfolio-Go/No-Go

## Referenzen

- `docs/production_10_10/asset_risk_tiers_and_leverage_caps.md`
- `docs/production_10_10/multi_asset_order_sizing_margin_safety.md`

## No-Go

Unsicheres Portfolio-Risiko oder unklare Korrelation blockieren Live-Openings.
