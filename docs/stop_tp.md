# Shared Exit Engine: Stop-Loss, TP, Break-Even, Trailing

**Policy-Version:** `shared-exit-v2` — vereinheitlichter Fachpfad, Time-Stop, Emergency-Flatten, erweiterte Validierung. Details: [exit_engine_unified.md](./exit_engine_unified.md).

## Trigger-Typen (Bitget-Semantik)

| Typ          | Bedeutung (Simulation)                                             |
| ------------ | ------------------------------------------------------------------ |
| `mark_price` | Trigger-Preis = Mark-Preis (Liquidations-/Risk-Nähe wie Exchange). |
| `fill_price` | Trigger-Preis = Last / `last_pr` (Order-Ausführung als Taker).     |

`executePrice=0` + Market-Execution auf Bitget entspricht hier der Bewertung gegen `mark_price` bzw. Fill-Proxy pro Tick.

## Stop-Methoden

1. **Volatility-aware**: `entry ± ATR × ATR_MULT_TF` (ATR aus `features.candle_features`, Fallback: letzte Kerze H−L, sonst `DEFAULT_ATR_FALLBACK_BPS`).
2. **Invalidation**: letzte Swing-Zone bzw. `stop_zone`-Drawing mit `STOP_PAD_BPS`.
3. **Liquidity-aware**: Kandidaten-Stop vs. Orderbook-Cluster (`tsdb.orderbook_top25`); Verschiebung um `LIQ_STOP_ESCAPE_BPS` bei hoher Notional-Dichte im Scan-Band.

Kombination: Long nimmt den **höchsten** Kandidaten-Stop (engster sinnvoller Schutz), Short analog **niedrigsten**.

## Stop Quality Score (0–100)

Start 100, Abzüge (deterministisch, siehe `quality_score.py`):

- −30 wenn Stop-Distanz &lt; `STOP_MIN_ATR_MULT × ATR`
- −20 wenn Liquidity-Basis `distance_bps` &lt; `LIQ_STOP_AVOID_BPS`
- −20 wenn RR &lt; `MIN_RR_FOR_TRADE` (aus TP1 vs. Stop)
- −10 bei hohem ATR% (`atrp_14` &gt; 2 %)

Clamp 0–100. Warnungen werden im Plan unter `quality.risk_warnings` gespeichert und als `events:risk_alert` veröffentlicht.

## Gemeinsamer Exit-Contract

- `signal-engine` baut aus Drawings einen gemeinsamen Exit-Preview mit `stop_loss`,
  `take_profit`, `take_profit_targets_json`, `stop_plan_json`, `tp_plan_json`
  und `exit_plan_validation`.
- `paper-broker` übernimmt dieselben Stop-/Target-Preise und dieselbe
  Break-Even-/Trailing-State-Logik, führt Teil-Schließungen aber als
  **market_on_trigger** aus.
- `live-broker` persistiert denselben Plan im Decision-Journal und leitet daraus
  reduce-only Ziel-Orders (`resting_until_hit`) plus Stop-/Trail-Flatten
  (`market_on_trigger`) ab.

## Take-Profit, Break-Even & Runner

- Drei Stufen **TP1 / TP2 / TP3** mit `EXIT_TP1_PCT`, `EXIT_TP2_PCT`,
  `EXIT_TP3_PCT` (Anteile am **initial_qty**).
- Ziele aus Drawings (`target_zone`, `resistance_zone`, `support_zone`) wenn
  genug Zonen vorhanden sind; sonst ATR-Multiples 0.8 / 1.6 / 3.0.
- **Break-Even** wird nach `EXIT_BREAK_EVEN_AFTER_TARGET_INDEX` aktiviert.
- **Runner / Trailing** wird nach `EXIT_TRAILING_ARM_AFTER_TARGET_INDEX`
  aktiviert; Trailing verwendet `EXIT_RUNNER_TRAIL_ATR_MULT` mit
  High-/Low-Water-Marks.
- `RUNNER_TRAIL_HIT` schließt die Restposition wie ein Stop.

## API

- `POST /paper/positions/{id}/plan/auto` — JSON: `timeframe`, optional `preferred_trigger_type`, `method_mix`
- `GET /paper/positions/{id}/plan`
- `POST /paper/positions/{id}/plan/override` — JSON: `stop_plan`, `tp_plan` (partielle Overrides)

## Events & Audit

- Redis:
  `events:signal_created` (inkl. Exit-Preview),
  `events:trade_updated` (TP, `tp_index`),
  `events:trade_closed` (SL / Runner),
  `events:risk_alert`
- Postgres:
  `paper.position_events` (`PLAN_CREATED`, `PLAN_UPDATED`, `TP_HIT`, `SL_HIT`,
  `TRAILING_UPDATE`, `RUNNER_TRAIL_HIT`)
  sowie `live.execution_decisions.payload_json.exit_engine` /
  `trace_json.exit_engine` fuer die Live-Auditspur.

## ENV

Siehe `.env.example` (Abschnitt Paper-/Live-Exit):
`PAPER_STOP_TP_ENABLED`, `EXIT_STOP_TRIGGER_TYPE_DEFAULT`,
`EXIT_TP_TRIGGER_TYPE_DEFAULT`, `EXIT_BREAK_EVEN_AFTER_TARGET_INDEX`,
`EXIT_TRAILING_ARM_AFTER_TARGET_INDEX`, `EXIT_TP1_PCT`, `EXIT_TP2_PCT`,
`EXIT_TP3_PCT`, `EXIT_RUNNER_TRAIL_ATR_MULT` sowie die ATR-/LIQ-Parameter.
Die frueheren Paper-Aliase (`STOP_TRIGGER_TYPE_DEFAULT`, `TP1_PCT` usw.)
bleiben kompatibel, sind aber nicht mehr der kanonische Konfigurationspfad.
