# Asset Risk Tiers und Order Sizing

## 1. Zielbild Multi-Asset-Risk

Die Main-Console und alle Trading-Pfade behandeln jedes Bitget-Asset strikt
asset-spezifisch. Es gibt keine globale "einheitliche" Live-Freigabe mehr.
Unklare oder fehlende Risk-Kontexte blockieren fail-closed.

## 2. Risk-Tier-Modell

Die zentrale Logik liegt in `shared/python/src/shared_py/asset_risk_tiers.py`.

- `RISK_TIER_0_BLOCKED`
- `RISK_TIER_1_MAJOR_LIQUID`
- `RISK_TIER_2_LIQUID`
- `RISK_TIER_3_ELEVATED_RISK`
- `RISK_TIER_4_SHADOW_ONLY`
- `RISK_TIER_5_BANNED_OR_DELISTED`

Jedes Tier definiert:

- erlaubte Modi (`paper`/`shadow`/`live`)
- `max_leverage`
- `max_position_notional_usdt`
- `max_risk_per_trade_0_1`
- `max_daily_loss_contribution_usdt`
- `required_liquidity_status`
- `required_data_quality_status`
- `required_strategy_evidence`
- `required_owner_approval`
- `default_action_on_uncertainty=block`

## 3. Live-Eligibility pro Tier

Harte Regeln:

1. Tier 0 blockiert Live.
2. Tier 4 ist Shadow-only.
3. Tier 5 blockiert alle Modi.
4. Live braucht Datenqualitaet `data_ok`.
5. Live braucht Liquiditaetsstatus `green`.
6. Live braucht Strategy-Evidence.
7. Live braucht frischen Account-/Portfolio-Kontext.
8. Live braucht Owner-Freigabe (Philipp).
9. Unknown Tier blockiert.
10. Asset ohne Tier blockiert.

## 4. Leverage-Caps

Tier-basierte Leverage-Caps:

- Tier 1: bis 25x
- Tier 2: bis 14x
- Tier 3: bis 8x
- Tier 4: bis 4x (nur Shadow/Paper)
- Tier 0/5: effektiv kein Live-Leverage

`validate_multi_asset_order_sizing(...)` erzwingt diese Caps zentral.

## 5. Positionsgroessen-Regeln

Tier-basierte Notional-Caps:

- Tier 1: 20_000 USDT
- Tier 2: 10_000 USDT
- Tier 3: 4_000 USDT
- Tier 4: 1_500 USDT
- Tier 0/5: 0 USDT

Ueberschreitung fuehrt zu `position_notional_above_tier_cap` und Block.

## 6. Margin-Regeln

Leverage und Notional werden gemeinsam mit bestehender Margin-/Drawdown-Logik
des Risk-Governors bewertet. Asset-Tier-Gates kommen zusaetzlich als harte
Reasons dazu und koennen Trade-Aktionen auf `do_not_trade` setzen.

## 7. Volatilitaetsregeln

`classify_asset_risk_tier(...)` fuehrt automatische Downgrades bzw. Blockierung
aus:

- sehr hohe Volatilitaet (`>=0.85`) -> Tier 0
- erhoehte Volatilitaet (`>=0.65`) -> Down-Tiering (z. B. Tier 1 -> Tier 2)

## 8. Spread-/Slippage-Regeln

- breiter Spread (`>120 bps`) klassifiziert auf Tier 0
- Live-Eligibility blockiert bei `spread_too_wide`

Damit sind illiquide/teure Ausfuehrungen fail-closed gesperrt.

## 9. Portfolio-Regeln

Asset-Tier-Gates ersetzen keine Portfolio-Gates. Live bleibt zusaetzlich von
Portfolio-Stress, Drawdown-, Exposure- und Korrelation-Limits abhaengig.

## 10. Main-Console-Anzeige

Die Main Console soll je Asset mindestens anzeigen:

- `asset_risk_tier`
- `asset_live_block_reasons_json`
- Tier-Caps (Leverage/Notional)
- Status fuer Datenqualitaet, Liquiditaet, Strategy-Evidence, Owner-Freigabe

## 11. Tests

- `tests/risk/test_asset_risk_tiers.py`
- `tests/security/test_multi_asset_order_sizing_live_blocking.py`
- `tests/tools/test_check_asset_risk_tiers.py`

## 12. No-Go-Regeln

- Kein Live bei fehlendem/unknown Tier.
- Kein Live bei Tier 0, Tier 4 oder Tier 5.
- Kein Live bei fehlender Datenqualitaet/Liquiditaet/Evidence/Owner-Freigabe.
- Keine globale Leverage-/Sizing-Policy ohne Asset-Tier-Guard.
