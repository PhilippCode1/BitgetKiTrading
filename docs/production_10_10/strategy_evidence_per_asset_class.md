# Strategy- und Signal-Evidence pro Asset-Klasse

## Warum keine globale Auto-Live-Strategie

Eine Strategie darf nicht automatisch fuer alle Assets live gehen. BTC- oder
Top-Liquid-Ergebnisse sind nicht auf illiquide, neue oder delisting-nahe Assets
uebertragbar.

## Asset-Klassen

- top_liquid_futures
- major_spot
- mid_liquidity
- high_volatility
- low_liquidity
- new_listing
- delisting_risk
- unknown

`unknown` blockiert Live immer fail-closed.

## Evidence-Stufen

- missing
- research_only
- backtest_available
- walk_forward_available
- paper_available
- shadow_available
- shadow_passed
- live_candidate
- live_allowed
- rejected
- expired

## Backtest/Paper/Shadow/Live

- Backtest allein reicht nicht.
- Paper allein reicht nicht.
- Shadow-Evidence muss asset- oder asset-klassenbezogen sein.
- Auch bei `shadow_passed` gilt: nur naechster Gate-Schritt, kein Auto-Live.

## Scope-Matching

Strategy-Evidence muss zu Asset/Asset-Klasse, MarketFamily, Risk-Tier und
Datenqualitaet passen.

## Evidence-Expiry

Abgelaufene Evidence (`expired`) blockiert Live.

## Main-Console-Anzeige

Die Main Console soll pro Asset/Signal anzeigen:

- Strategie + Version + Playbook
- Asset-Klasse
- Evidence-Status
- fehlende Evidence
- Live-Blockgruende
- deutsche Erklaerung "warum blockiert/warum naechster Gate-Schritt"

## Referenzen

- `docs/production_10_10/asset_risk_tiers_and_leverage_caps.md`
- `docs/production_10_10/multi_asset_order_sizing_margin_safety.md`

## No-Go

Fehlende, abgelehnte, abgelaufene oder scope-falsche Strategy-Evidence blockiert
Live-Opening.
