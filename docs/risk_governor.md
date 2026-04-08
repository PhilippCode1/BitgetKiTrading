# Risk-Governor und Leverage-Allocator (7..75)

Implementierung: `services/signal-engine/src/signal_engine/risk_governor.py` (**Version `risk-governor-v2`**),
`signal_engine/portfolio_risk.py`, eingebunden in `hybrid_decision.py` (Policy `hybrid-v4`).

## Globale Reihenfolge

1. **Universal-Hard vs. Live-Execution** — Default (`RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY=true`):
   - **Signalweit** (`hard_block_reasons_json` / Hybrid Safety-Floor): `uncertainty_gate_phase == blocked`, `exchange_health_ok == false`.
   - **Nur Echtgeld** (`live_execution_block_reasons_json`): Margin, Drawdowns, taeglicher Realized-Loss, Verlustserie,
     Korrelationsstress, parallele Positionen, Brutto-Exposure, Side-Policy, Portfolio-/Venue-Felder aus
     `portfolio_risk_json` (siehe `docs/portfolio_risk_governor.md`). Live-Broker bricht Submit bei nicht-leerer Liste ab.
   - Legacy: `RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY=false` legt Konto-Stress wieder in `hard_block_reasons_json`.
2. **Max-Exposure / Positionsgroesse** — Qualitaets-Tier **A–D** mit `max_exposure_fraction_0_1` (1.0 / 0.65 / 0.35 / 0.20).
3. **Hebel 7..75** — Tier-Basisdeckel, dann Verschaerfung bei Unsicherheit, OOD, Datenqualitaet, Spread, Liquiditaet; danach Hybrid-Faktor-Caps (`risk_governor_cap` in `factor_caps`). **Live-Ramp:** Meta-Lane `candidate_for_live` ohne Freigabe im Snapshot: `allowed_leverage` und `recommended_leverage` auf `RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE` (Default 7).

**Danach:** Unified Allocator (`docs/unified_leverage_allocator.md`) setzt `execution_leverage_cap` und `mirror_leverage` sowie Notional-Shrink; er wird nach dem Stop-Budget-Assessment mit echter Stop-Distanz neu berechnet.

## Account-Snapshot (optional)

Unter `source_snapshot_json.risk_account_snapshot` (JSON-Objekt), z. B.:

- `margin_utilization_0_1`, `account_drawdown_0_1`, `daily_drawdown_0_1`, `weekly_drawdown_0_1`
- `daily_realized_loss_usdt`, `consecutive_losses`, `portfolio_correlation_stress_0_1`
- `exchange_health_ok` (bool, `false` = **signalweiter** Stopp)
- `open_positions_count`, `gross_exposure_ratio_0_1`
- `allowed_entry_sides`: `["long"]` / `["short"]` / beides — bei `LIVE_ONLY` nur Live-Block
- **Hebel-Freigabe:** `leverage_escalation_approved`, `measurably_stable_for_escalation` (beide `true` hebt Live-Ramp auf)
- **`portfolio_risk_json`**: siehe `docs/portfolio_risk_governor.md`

Fehlende Keys: kein Gate auf diesem Feld (konservativ nur ueber Signal-/Marktdaten).

## Mapping (Ausgabe)

| Feld                                | Bedeutung                                                                         |
| ----------------------------------- | --------------------------------------------------------------------------------- |
| `hard_block_reasons_json`           | Universal-Hard; nicht leer => Hybrid Safety-Floor (`do_not_trade`)                |
| `universal_hard_block_reasons_json` | Nur Unsicherheit/Exchange-Health (Audit)                                          |
| `live_execution_block_reasons_json` | Konto/Portfolio: blockt Live-Broker, Paper/Shadow bei `LIVE_ONLY` weiter moeglich |
| `portfolio_risk_synthesis_json`     | Kompakte Synthese fuer Operator/Dashboard                                         |
| `trade_action_recommendation`       | `allow_trade` / `do_not_trade` (Hinweis; Hybrid setzt final)                      |
| `allowed_side`                      | `none` / `long` / `short` / `both`                                                |
| `max_exposure_fraction_0_1`         | Deckel fuer Positionsgroesse relativ zum Kontext                                  |
| `max_leverage_cap`                  | Obergrenze vor Hybrid-Allocator                                                   |
| `exit_strategies_allowed_json`      | Erlaubte Exit-Modi (strenger bei Tier D / Hard-Block)                             |
| `emergency_rules_json`              | Notfallflags (Flatten bei Margin, Exchange degraded, …)                           |

Audit: `hybrid_decision.risk_governor` in `source_snapshot_json`; gekuerzt in `reasons_json.hybrid_decision` (Version, Exposure-Fraktion, Exit-Liste).

## Qualitaetsmatrix (Kurz)

| Tier | Basis-Hebel-Cap | Exposure-Fraktion |
| ---- | --------------- | ----------------- |
| A    | 75              | 1.0               |
| B    | 35              | 0.65              |
| C    | 14              | 0.35              |
| D    | 7               | 0.20              |

Zusaetzliche Abschlaege: hohe `model_uncertainty_0_1`, OOD-Score/Alert, schlechte Datenqualitaet, weiter Spread, schwache Tiefe / kein Orderbook-`liquidity_source`.
