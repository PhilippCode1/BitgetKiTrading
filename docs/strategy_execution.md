# Strategy Execution Layer (Prompt 20)

## Überblick

Der `paper-broker` konsumiert Redis-Streams und kann bei erfüllten Gates automatisch Paper-Positionen eröffnen, Stop/TP anwenden und Risiko-Ereignisse (News, Struktur, Drawings) behandeln. Seit Prompt 23 kommen Stop-Loss, Partial-TP, Break-Even und Trailing dabei aus derselben Shared-Exit-Logik wie im `live-broker`.

## Kill-Switch & Consumer

- **`STRATEGY_EXEC_ENABLED=false`**: keine automatischen Aktionen aus Signalen/News/Drawings/Struktur; `market_tick` + Funding laufen weiter, wenn der Consumer aktiv ist.
- **`POST /strategy/pause`** / **`POST /strategy/resume`**: setzt `paper.strategy_state.paused` pro Symbol (Key = Symbol, z. B. `<example_symbol>`).
- **`PAPER_SIM_MODE`**: Wenn `true` **und** `STRATEGY_EXEC_ENABLED=false`, startet kein Redis-Consumer. Mit `STRATEGY_EXEC_ENABLED=true` startet der Consumer auch im Sim-Modus (Redis muss erreichbar sein).

## Strategy Registry (V1)

| Strategie                    | `signal_class`   |
| ---------------------------- | ---------------- |
| `MeanReversionMicroStrategy` | `mikro`          |
| `TrendContinuationStrategy`  | `kern` (Default) |
| `BreakoutBoxStrategy`        | `gross`          |

Jede Strategie: `should_enter`, `build_order_intent` (Side, Qty, Leverage, `market`).

## Gating (deterministisch)

Vor Auto-Open nutzt `paper-broker` jetzt dieselbe fachliche Risk-Basis wie der
`live-broker` (Shared-Risk-Engine):

- `decision_state` / `final_decision_state` == `accepted`
- `rejection_state` nicht aktiv, keine `rejection_reasons_json`
- `signal_strength_0_100` ≥ `RISK_MIN_SIGNAL_STRENGTH`
- `probability_0_1` ≥ `RISK_MIN_PROBABILITY`
- `risk_score_0_100` ≥ `RISK_MIN_RISK_SCORE`
- `expected_return_bps` ≥ `RISK_MIN_EXPECTED_RETURN_BPS`
- `expected_mae_bps` ≤ `RISK_MAX_EXPECTED_MAE_BPS`
- `expected_mfe_bps / expected_mae_bps` ≥ `RISK_MIN_PROJECTED_RR`
- harte Blockierung bei `market_regime=shock`, Staleness-/Quality-Gate-Faellen,
  `allowed_leverage < 7`, Konto-/Margin-/Drawdown-Limits und zu vielen
  gleichzeitigen Positionen

Fehlende Felder im Event-Payload werden aus `app.signals_v1` per `signal_id` ergänzt, falls vorhanden.

## Sizing

- `kern`: `STRAT_BASE_QTY_BTC`
- `mikro`: × `MICRO_SIZE_MULT`
- `gross`: × `GROSS_SIZE_MULT`
- `warnung`: kein Open; offene Position + Warnung gegen Richtung → optional De-Risk (`CLOSE_PARTIAL_ON_NEWS_SHOCK_PCT`)

## News-Shock

Bei `events:news_scored`:

- `impact_window` ∈ {`immediate`, `sofort`, `instant`}
- `relevance_score` ≥ `NEWS_SHOCK_SCORE`
- Sentiment **gegen** Position (`baerisch`/`bear` vs. Long, `bullisch`/`bull` vs. Short)

→ `events:risk_alert`, `risk_off_until_ts_ms` = jetzt + `NEWS_COOLDOWN_SEC`, optional Partial/Full Close.

## Ziel-Nachführung (Drawings)

Bei `events:drawing_updated` mit `parent_ids`: TP2/TP3 werden nur angehoben/abgesenkt (in Gewinnrichtung), wenn `USE_DRAWING_TARGET_UPDATES=true` und RR nicht schlechter wird (Toleranz siehe Code). Audit: `paper.position_events` (`PLAN_UPDATED`), `paper.strategy_events` (`DRAWING_TP_UPDATE`).

## Struktur-Widerspruch

Bei `events:structure_updated`: Trend `trend_dir` `1` / `-1` (String) vs. Position → bei `USE_STRUCTURE_FLIP_EXIT`: entweder Full Close (`STRUCTURE_FLIP_FULL_CLOSE=true`) oder Stop anziehen (`STRUCTURE_FLIP_TIGHTEN_BPS`).

## Trade-Management pro Tick

- Stop-Loss hat Prioritaet vor TP/Runner.
- TP-Hits laufen sequentiell ueber denselben Shared-Exit-Core wie Live; die
  Teilmengen kommen aus `take_pct` und der initialen Positionsgroesse.
- Nach TP1 setzt die Shared-Exit-Logik den Stop auf Break-Even
  (`PLAN_UPDATED`, Quelle `break_even_after_tp1`).
- Nach TP2 wird der Runner bewaffnet; das Trailing arbeitet ueber einen festen,
  im Plan persistierten `trail_offset`, damit Paper und Live dieselbe
  Exit-Semantik verwenden.
- Exit-Overrides (`plan_override`) werden vor Persistenz gegen Shared-Risk und
  Leverage validiert.

## API

| Methode | Pfad                                                 |
| ------- | ---------------------------------------------------- |
| GET     | `/strategy/status?symbol=<example_symbol>`           |
| POST    | `/strategy/pause` `{ "symbol": "<example_symbol>" }` |
| POST    | `/strategy/resume`                                   |
| GET     | `/strategy/rules`                                    |
| GET     | `/paper/trades/recent?limit=20`                      |

## Fixture

```bash
python tools/publish_signal_fixture.py
```

ENV-Overrides: `FIXTURE_SYMBOL`, `FIXTURE_CLASS`, `FIXTURE_STRENGTH`, …

## Migration

`130_strategy_execution.sql` → `paper.strategy_state`, `paper.strategy_events`.

Erweiterung **560_paper_broker_multi_asset_audit.sql**: zusaetzliche `strategy_events`-Typen
(`AUTO_BLOCKED`, `NO_TRADE_GATE`, `PLAN_SNAPSHOT`, `POST_TRADE_REVIEW_READY`, …) und
Positions-Spalten `signal_id`, `canonical_instrument_id`, `market_family`, `product_type`
fuer Lern-/Mirror-Joins. `NO_TRADE_GATE` protokolliert explizite Abbruiche der Auto-Pipeline
(Gates, Registry, Strategie, Warnung-gegen-Position).

Paper-Broker laedt Kontraktkontext **signalbezogen** (`market_family`, `product_type`, … aus
`app.signals_v1` / Event), sofern `BitgetInstrumentCatalog` angebunden ist. Optional:
`PAPER_REQUIRE_CATALOG_TRADEABLE=true`, damit nur boersenseitig handelbare Instrumente
geoeffnet werden.
