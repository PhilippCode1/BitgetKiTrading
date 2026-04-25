# Multi-Asset Order-Sizing und Margin-Safety

## Signal, Size und Live-Submit

Ein Signal ist keine Order. Vor Live-Submit wird eine konservative Groesse
berechnet und gegen Risk-, Margin-, Liquiditaets- und Instrument-Gates geprueft.

## Pflichtkontext

- Asset/Symbol, Market-Family
- Risk-Tier und Liquiditaets-Tier
- frische Account-Equity und Available Margin
- Daily-/Weekly-Loss, Drawdown
- Stop-Distanz, Slippage, Fees/Funding
- Leverage-Cap
- Instrument-Min/Max/Precision
- offene Positionen und Pending Orders

## Harte Sizing-Regeln

1. Kein Sizing ohne frische Equity.
2. Kein Sizing ohne Instrumentkontext.
3. Kein Sizing ohne Risk-Tier.
4. Kein Sizing ohne Liquiditaetsstatus.
5. Keine Groesse ueber Margin-Limit.
6. Keine Groesse ueber Position-Risk-Limit.
7. Daily-/Weekly-Loss- oder Drawdown-Breach blockiert.
8. MinQty/MinNotional werden strikt geprueft.
9. Precision-Rounding darf Risiko nicht erhoehen.
10. Live-Sizing konservativer als Paper/Shadow.
11. Bei Unsicherheit: `size=0` und `do_not_trade`.

## Asset-Tier- und Liquidity-Caps

Tier- und Liquiditaets-Caps reduzieren Notional dynamisch.
Risk Tier D/E fuehrt zu `size=0`.

## Main-Console Anzeige „Order-Sizing & Margin“

Pro Signal/Asset sichtbar:

- vorgeschlagene Groesse
- max erlaubte Groesse
- risk per trade
- leverage cap
- margin usage
- block reason
- warum Groesse reduziert wurde

## Referenzen

- `docs/production_10_10/asset_risk_tiers_and_leverage_caps.md`
- `docs/production_10_10/instrument_precision_order_contract.md`

## No-Go

Unsichere Positionsgroessen duerfen nie in Live-Submit muenden.
