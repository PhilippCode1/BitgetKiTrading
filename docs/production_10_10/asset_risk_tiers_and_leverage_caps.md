# Asset-Risk-Tiers und dynamische Leverage-Caps

## Warum Asset-Tiers noetig sind

BTC/ETH und kleine volatile Assets duerfen nicht mit denselben Hebel- und
Groessenregeln behandelt werden. Multi-Asset-Live braucht risikoklassenbasierte
Caps und fail-closed Defaults.

## Definierte Risk-Tiers

- **Risk Tier A**: sehr liquide, niedrige Volatilitaet, enge Spreads
- **Risk Tier B**: liquide Assets mit moderater Volatilitaet
- **Risk Tier C**: mittlere Liquiditaet/erhoehtes Risiko
- **Risk Tier D**: hohe Volatilitaet/geringe Liquiditaet, kein Live-Opening
- **Risk Tier E**: blockiert/quarantine/unknown/delisted/suspended

## Inputs fuer Tier-Klassifikation

- `market_family`
- `liquidity_tier`
- `data_quality_status`
- Volatilitaetsmetriken
- Funding-/OI-Risiko
- Delisting-/Suspension-Status
- Strategy-Evidence-Status

Tier darf nie nur aus dem Symbolnamen entstehen.

## Dynamische Leverage-Caps

Beispielhafte Zielcaps:

- Tier A: bis 25x (Live-Startphase konservativer)
- Tier B: bis 14x
- Tier C: bis 8x
- Tier D: bis 4x, kein Live-Opening
- Tier E: 1x/0 Notional, blockiert

Hohe Volatilitaet reduziert den effektiven Hebel zusaetzlich.

## Live-Regeln

- Tier E blockiert alles ausser Anzeige/Historie.
- Tier D darf nicht live eroeffnen.
- Tier C braucht besondere Evidence + Owner-Review + konservative Groesse.
- Tier A/B nur mit gruenen Gates (Datenqualitaet, Liquiditaet, Strategy-Evidence,
  Exchange, Reconcile, Owner).
- `live_allowed` ist nie Default-`true`.

## Main-Console-Anzeige

Modul **Asset-Risk** zeigt pro Asset:

- Risk Tier
- Max-Leverage-Cap
- Max-Notional
- Gruende/Blocker auf Deutsch
- ob Owner-Review erforderlich ist

## Referenzen

- `docs/production_10_10/asset_quarantine_and_live_allowlist.md`
- `shared/python/src/shared_py/asset_risk_tiers.py`

## No-Go

Kein Echtgeld-Live fuer unknown/high-risk Assets ohne explizite, verifizierte
Freigaben.
