# Portfolio-Risiko und Live-Execution (risk-governor-v2)

## Zweck

Konto-Stress (Margin, Drawdowns, Verlustserie, Korrelation, Konzentration) und strukturelle Portfolio-Signale
(Family-Exposure, Richtungsbias, korrelierte Cluster, Funding/Basis, Session-Konzentration, offene Orders,
pending Mirror-Trades, Venue-Modus) sollen **Echtgeld** zuverlaessig blockieren, ohne Paper/Shadow-Lernpfade
willkuerlich abzuschalten — solange `RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY=true` (Default).

Siehe auch: `docs/risk_governor.md`, `docs/unified_leverage_allocator.md`.

## Snapshot-Kontrakt

### `risk_account_snapshot` (bestehend)

Alle bisherigen Kontokennzahlen bleiben gueltig. Zusaetzlich optional:

### `risk_account_snapshot.portfolio_risk_json`

| Feld                                      | Typ    | Semantik                                                                                   |
| ----------------------------------------- | ------ | ------------------------------------------------------------------------------------------ |
| `venue_operational_mode`                  | string | `degraded` blockt Live, wenn `RISK_PORTFOLIO_LIVE_BLOCK_VENUE_DEGRADED=true`               |
| `symbol_family`                           | string | Fallback fuer Family-Exposure, falls `market_family` am Signal fehlt                       |
| `family_exposure_fraction_0_1`            | object | z. B. `{"futures":0.45,"margin":0.1,"spot":0.02}` — Vergleich gegen Signal-`market_family` |
| `direction_net_exposure_0_1`              | number | Netto-Richtungskonzentration 0..1                                                          |
| `correlated_cluster_largest_exposure_0_1` | number | groesster korrelierter Cluster                                                             |
| `funding_drag_bps_next_8h`                | number | adverse Funding-Drag in bps (nur wenn > Schwelle)                                          |
| `basis_stress_0_1`                        | number | Basis-/Perp-Spot-Stress 0..1                                                               |
| `session_event_concentration_0_1`         | number | Session-/Event-Ueberlagerung                                                               |
| `open_orders_notional_to_equity_0_1`      | number | offene Orders vs. Equity                                                                   |
| `pending_mirror_trades_count`             | int    | ausstehende Mirror-/Freigabe-Pipeline                                                      |

**Fehlende Felder:** kein Gate — Feed muss vom Monitor/Account-Sync kommen; ohne Daten keine Portfolio-Haerte auf diesem Feld.

## ENV-Schwellen (BaseServiceSettings)

- `RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY` (default `true`)
- `RISK_PORTFOLIO_LIVE_MAX_FAMILY_EXPOSURE_0_1`
- `RISK_PORTFOLIO_LIVE_MAX_DIRECTION_NET_EXPOSURE_0_1`
- `RISK_PORTFOLIO_LIVE_MAX_CLUSTER_EXPOSURE_0_1`
- `RISK_PORTFOLIO_LIVE_MAX_FUNDING_DRAG_BPS`
- `RISK_PORTFOLIO_LIVE_MAX_BASIS_STRESS_0_1`
- `RISK_PORTFOLIO_LIVE_MAX_SESSION_CONCENTRATION_0_1`
- `RISK_PORTFOLIO_LIVE_MAX_OPEN_ORDERS_NOTIONAL_RATIO_0_1`
- `RISK_PORTFOLIO_LIVE_MAX_PENDING_MIRROR_TRADES`
- `RISK_PORTFOLIO_LIVE_BLOCK_VENUE_DEGRADED`

## Ausgabe im Governor

- `universal_hard_block_reasons_json` — signalweit (Hybrid Safety-Floor): u. a. `uncertainty_gate_phase == blocked`, `exchange_health_ok == false`
- `live_execution_block_reasons_json` — Konto-Stress + Portfolio-Structural; **Live-Broker** bricht bei nicht-leerer Liste ab (`portfolio_live_execution_policy`)
- `hard_block_reasons_json` — bei `LIVE_ONLY=true` identisch zu universal; bei Legacy (`false`) Vereinigung aus universal + live
- `portfolio_risk_synthesis_json` — kompakte Operator-/Audit-Sicht

## Operator-Sicht

- Dashboard-Signaldetail: Universal vs. Live-Blocker
- Alert-Engine: `LIVE_EXECUTION_POLICY_WARN` wenn `trade_action=allow_trade` aber Live-Blocker gesetzt
- API: `fetch_signal_by_id` liefert `live_execution_block_reasons_json`, `governor_universal_hard_block_reasons_json`, `live_execution_clear_for_real_money`

## Migration

`infra/migrations/postgres/530_portfolio_live_execution_audit.sql` — Kommentar/Abnahmehinweis (keine neuen Spalten).
