# Portfolio Risk Drill Guide

## Zweck

Dieser Drill zeigt fail-closed, dass neue Opening-Orders blockiert werden, sobald Portfolio-Risiko, Verlustgrenzen oder Drawdown-Limits verletzt sind.

## Owner-Limits (Pflicht)

Philipp muss `docs/production_10_10/owner_risk_limits.template.json` ausfuellen:

- `max_daily_loss_percent`
- `max_weekly_loss_percent`
- `max_total_drawdown_percent`
- `max_position_notional_usd`
- `max_total_notional_usd`
- `max_open_positions`
- `max_leverage_initial`
- `max_leverage_after_burn_in`
- `allowed_asset_tiers`
- `blocked_assets`
- `reviewed_at`
- `status`
- `signature_reference`

## Empfohlene Startgrenzen (konservativ)

- Daily Loss: 1.0% bis 1.5%
- Weekly Loss: 2.5% bis 3.5%
- Total Drawdown: 6% bis 8%
- Initial Leverage: maximal 7x

## Drill ausfuehren

```bash
python scripts/portfolio_risk_drill_report.py --output-md reports/portfolio_risk_drill.md --output-json reports/portfolio_risk_drill.json
python scripts/portfolio_strategy_evidence_report.py --output-md reports/portfolio_strategy_evidence.md --output-json reports/portfolio_strategy_evidence.json
python scripts/risk_execution_evidence_report.py --output-md reports/risk_execution_evidence.md --output-json reports/risk_execution_evidence.json
```

## Reports

- `reports/portfolio_risk_drill.md`
- `reports/portfolio_risk_drill.json`
- `reports/portfolio_strategy_evidence.md`
- `reports/portfolio_strategy_evidence.json`
- `reports/risk_execution_evidence.md`
- `reports/risk_execution_evidence.json`

## Abgedeckte Szenarien

1. Normalzustand
2. Max Asset Exposure verletzt
3. Max Family Exposure verletzt
4. Max Correlation Exposure verletzt
5. Daily Loss Limit erreicht
6. Weekly Loss Limit erreicht
7. Drawdown Limit erreicht
8. Loss Streak Limit erreicht
9. Global Halt aktiv
10. Risk State unknown
11. Reduce-only nach Loss Limit
12. Opening Order nach Halt blockiert

## Wann `portfolio_risk` verified werden darf

Nur mit echten, owner-signierten Limits und einem echten Staging-/Shadow-Runtime-Drill mit nachvollziehbaren Audit-Artefakten.

## Warum Live ohne Owner-Limits und Drill NO_GO bleibt

Ohne diese Evidence ist die Verlust- und Gesamtrisiko-Kontrolle nicht institutionell nachgewiesen. Daher bleibt `private_live_allowed=NO_GO`.
