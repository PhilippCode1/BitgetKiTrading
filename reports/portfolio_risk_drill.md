# Portfolio Risk Drill Report

- Generiert: `2026-04-26T09:48:25Z`
- Git SHA: `339dd15`
- Status: `implemented`
- Decision: `NOT_ENOUGH_EVIDENCE`
- Verified: `False`
- Evidence-Level: `synthetic`

- `normalzustand`: expected=ALLOW_OPENING actual=ALLOW_OPENING pass=True reasons=-
- `max_asset_exposure_verletzt`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=asset_exposure_ueber_limit
- `max_family_exposure_verletzt`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=family_exposure_zu_hoch
- `max_correlation_exposure_verletzt`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=correlation_group_exposure_zu_hoch
- `daily_loss_limit_erreicht`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=daily_loss_limit_erreicht
- `weekly_loss_limit_erreicht`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=weekly_loss_limit_erreicht
- `drawdown_limit_erreicht`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=intraday_drawdown_limit_erreicht
- `loss_streak_limit_erreicht`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=loss_streak_limit_erreicht
- `global_halt_aktiv`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=global_halt_aktiv
- `risk_state_unknown`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=portfolio_snapshot_stale
- `reduce_only_nach_loss_limit`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=daily_loss_limit_erreicht
- `opening_order_nach_halt_blockiert`: expected=BLOCK_OPENING actual=BLOCK_OPENING pass=True reasons=global_halt_aktiv
