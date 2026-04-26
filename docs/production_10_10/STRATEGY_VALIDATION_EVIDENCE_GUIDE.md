# Strategy Validation Evidence Guide

## Zweck

Diese Anleitung beschreibt, welche Evidence pro Strategie und Asset-Klasse vorliegen muss, bevor `strategy_validation_per_asset_class` jemals auf `verified` gehen darf.

## Pflicht-Evidence

- Strategy-ID, Strategy-Version, Parameter-Hash, Git-SHA, `checked_at`
- Asset-Klasse, Market-Family, getestete Symbole, Zeitraum, Timeframe, Datenquelle
- Backtest inkl. Kostenannahmen (`fees`, `spread`, `slippage`, bei Futures `funding`)
- Kennzahlen: `number_of_trades`, `profit_factor`, `expectancy`, `max_drawdown`, `longest_loss_streak`, `risk_per_trade`
- Validierung: Out-of-sample, Walk-forward, Paper und Shadow
- Dokumentierte bekannte Failure-Modes und Marktphasenabdeckung

## Warum Backtest alleine nicht reicht

Backtests ohne Paper/Shadow zeigen nicht, wie Strategie, Ausfuehrung und Betriebsrisiken unter realen Feed- und Latenzbedingungen reagieren. Deshalb blockiert der Live-Pfad fail-closed.

## Mindestanforderungen

- Keine Live-Freigabe ohne Kosten/Slippage/Spread (und Funding bei Futures)
- Keine Live-Freigabe ohne Drawdown- und Verlustserien-Auswertung
- Keine Live-Freigabe ohne Out-of-sample und Walk-forward
- Keine Live-Freigabe ohne Paper- und Shadow-Evidence
- Keine Live-Freigabe ohne reproduzierbare Parameter und Version-Bindung
- Synthetische Evidence ist nie `verified`

## Kommandos

```bash
python scripts/strategy_asset_evidence_report.py --output-md reports/strategy_asset_evidence.md --output-json reports/strategy_asset_evidence.json
python scripts/verify_multi_asset_strategy_evidence.py --input-json tests/fixtures/multi_asset_strategy_evidence_sample.json --output-md reports/multi_asset_strategy_evidence.md --output-json reports/multi_asset_strategy_evidence.json --allow-failures
python scripts/portfolio_strategy_evidence_report.py --output-md reports/portfolio_strategy_evidence.md --output-json reports/portfolio_strategy_evidence.json --strict
```

## Reports

- `reports/strategy_asset_evidence.md` + `.json`
- `reports/multi_asset_strategy_evidence.md` + `.json`
- `reports/portfolio_strategy_evidence.md` + `.json`

## Wann `verified` erlaubt ist

Nur wenn pro Asset-Klasse echte Backtest-, Paper- und Shadow-Evidence mit reproduzierbarer Version-Bindung, Runtime-Traceability und Owner-Review vorliegt.

## Warum Live weiter NO_GO bleibt

Solange diese Evidence nicht fuer jede relevante Asset-Klasse extern belegt ist, bleibt `private_live_allowed=NO_GO` und `strategy_validation_per_asset_class` darf nicht `verified` werden.
