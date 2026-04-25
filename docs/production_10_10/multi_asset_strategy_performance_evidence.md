# Multi-Asset Strategie- und Performance-Evidence

## Ziel

Keine Strategie darf automatisch fuer alle Bitget-Assets live laufen. Jede
Asset-Klasse braucht eigene Evidence fuer Backtest, Walk-forward, OOS, Paper,
Shadow, Kosten, Drawdown und Ausfuehrungsqualitaet.

## Asset-Klassen

- `major_high_liquidity`
- `large_liquidity`
- `mid_liquidity`
- `high_volatility`
- `low_liquidity`
- `new_listing`
- `delisting_risk`
- `blocked_unknown`

## Pflicht-Evidence pro Asset-Klasse

1. Backtest
2. Walk-forward
3. Out-of-sample
4. Paper
5. Shadow
6. Slippage/Fees/Funding
7. Drawdown
8. Regime-Breakdown
9. Asset-Klassen-Breakdown
10. Trade Count
11. No-Trade-Qualitaet
12. Datenqualitaet
13. Liquidity Execution Evidence

## Bewertungslogik

- `PASS`: Evidence ausreichend.
- `PASS_WITH_WARNINGS`: kein harter Blocker, aber Warnhinweise (z. B. wenige Trades).
- `FAIL`: Live-Freigabe blockiert.

## Harte Regeln

- Backtest-only reicht nicht fuer Live.
- Paper-only reicht nicht fuer Live.
- Shadow-Burn-in pro Asset-Klasse ist Pflicht fuer Live.
- `new_listing`, `delisting_risk`, `blocked_unknown` bleiben blockiert/quarantaene.
- Low-liquidity ohne Ausfuehrungs-Evidence bleibt blockiert.
- Negative Expectancy nach Kosten blockiert.
- Hoher Drawdown blockiert.

## Script / Report

`scripts/verify_multi_asset_strategy_evidence.py`:

- `--dry-run`
- `--input-json tests/fixtures/multi_asset_strategy_evidence_sample.json`
- `--output-md reports/multi_asset_strategy_evidence_sample.md`
- optional `--output-json reports/multi_asset_strategy_evidence_sample.json`

Der Report liefert deutsche Entscheidungs- und Blockgruende pro Asset.

## Main-Console-Hinweis

Die Main Console soll ein Modul "Strategie-Evidence pro Asset-Klasse" fuehren:

- Welche Assets sind nur chart/paper/shadow/live?
- Welche Live-Freigaben bleiben blockiert?
- Welche Evidence fehlt je Asset-Klasse?

## Offener Anschluss

Echte Live-Freigaben brauchen spaeter produktive Backtest-/Walk-forward-,
Paper-, Shadow- und Execution-Daten je Asset-Klasse. Ohne diese Daten bleibt
Live-Freigabe fail-closed.
