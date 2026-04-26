# Risk Limits Owner Evidence Guide

Diese Anleitung definiert, welche Owner-Grenzen Philipp nachweisbar setzen muss, bevor `asset_risk_tiers`, `multi_asset_order_sizing` und `portfolio_risk` auf `verified` gehen duerfen.

## 1) Welche Owner-Limits festgelegt werden muessen

- Max-Leverage pro Asset-Tier
- Max-Notional pro Asset
- Max-Exposure pro Market-Family
- Max-Portfolio-Exposure und Drawdown-Limits
- Daily-/Weekly-Loss-Limits

## 2) Welche Max-Hebel in der Startphase gelten

- Burn-in Startgrenze: `7x`
- Jede Ueberschreitung ueber 7x braucht Owner-Freigabe + Evidence

## 3) Warum 7x Startgrenze bleibt

Die 7x-Grenze reduziert Ausfuehrungs- und Liquidationsrisiko in der fruehen Live-Phase. Ohne stabile Runtime-Evidence bleibt >7x blockiert.

## 4) Welche Asset-Tiers erlaubt sind

- `RISK_TIER_1_MAJOR_LIQUID`, `RISK_TIER_2_LIQUID`, `RISK_TIER_3_ELEVATED_RISK` nur mit vollen Gates
- `RISK_TIER_4_SHADOW_ONLY`, `RISK_TIER_5_BANNED_OR_DELISTED`, unknown -> kein Live

## 5) Welche Assets blockiert sind

- Assets ohne Tier
- Unknown/Delisted/Suspended/Blocked-Assets
- Assets ohne Owner-Freigabe wenn Tier dies verlangt

## 6) Wie Risk-Tier-Evidence erzeugt wird

```bash
python tools/check_asset_risk_tiers.py
python tools/check_asset_risk_tiers.py --strict-live
```

## 7) Wie Portfolio-Risk-Drill laeuft

- Limit-Breach-Szenarien fuer Exposure/Margin/Drawdown simulieren
- pruefen, dass neue Opening-Orders blockiert werden
- reduce-only darf nur sicher/offen begrenzt bleiben

## 8) Welche Reports entstehen

- `reports/risk_execution_evidence.md`
- `reports/risk_execution_evidence.json`
- optional kombiniert mit Asset- und Preflight-Evidence-Reports

## 9) Wann Kategorien `verified` werden duerfen

Nur mit:

- owner-signierten Limits (extern archiviert)
- Runtime-Snapshots aus Staging/Shadow
- dokumentiertem Zeitraum, Umgebung, Git-SHA
- erfolgreichem Drill fuer Risk/Sizing/Portfolio-Blocker

## 10) Warum Live ohne Owner-Limits NO_GO bleibt

Ohne verbindliche Owner-Limits ist Risk-Autorisierung unklar. Institutionsniveau verlangt eindeutige, nachweisbare Grenzen; daher bleibt `private_live_allowed` bis dahin `NO_GO`.
