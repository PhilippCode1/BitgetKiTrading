# Learning Engine V1 (Prompt 23)

Analytics über `learn.trade_evaluations`: Health-Metriken, Fehlermuster, Empfehlungen, Drift (ADWIN‑Idee), optional MLflow.

Seit Prompt 15 sind die kanonischen Learning-Targets am Entscheidungsanker
`decision_ts_ms` verankert. Return-/MAE-/MFE-/Liquidations-Labels werden nur
aus nachgelagerten Daten bis `closed_ts_ms` gebaut.

## Metriken (pro Strategie & Fenster)

Rollierende Fenster über `closed_ts_ms` (konfigurierbar via `LEARNING_WINDOW_LIST`, z. B. `1d,7d,30d`):

| Metrik                          | Definition                                                  |
| ------------------------------- | ----------------------------------------------------------- |
| `trades`                        | Anzahl Trades                                               |
| `win_rate`                      | `direction_correct` / trades                                |
| `gross_profit`                  | Summe positiver `pnl_net_usdt`                              |
| `gross_loss`                    | Summe negativer `pnl_net_usdt` (negativ)                    |
| `profit_factor`                 | `gross_profit / abs(gross_loss)` (ohne Division durch 0)    |
| `max_drawdown`                  | Max. relativer Drawdown auf kumulierter PnL‑Kurve (Start 0) |
| `stop_out_rate`                 | Anteil `stop_hit`                                           |
| `fee_drag`                      | `sum(fees) / (gross_profit + abs(gross_loss))`              |
| `funding_drag`                  | `sum(funding) / (gross_profit + abs(gross_loss))`           |
| `take_trade_rate`               | Anteil `take_trade_label = true`                            |
| `liquidation_risk_rate`         | Anteil `liquidation_risk = true`                            |
| `avg_expected_return_bps`       | Durchschnittliches Netto-Return-Target in bps               |
| `avg_expected_return_gross_bps` | Durchschnittliches Brutto-Return-Target in bps              |
| `avg_expected_mae_bps`          | Durchschnittliche adverse Excursion in bps                  |
| `avg_expected_mfe_bps`          | Durchschnittliche favourable Excursion in bps               |

Strategiezuordnung: `signal_snapshot_json.strategy_name` oder Fallback über `signal_class` → gleiche Namen wie Paper‑Broker (`MeanReversionMicroStrategy`, …). Metriken werden nur für Einträge in `learn.strategies` persistiert (`learn.strategy_metrics`).

## Fehlermuster (deterministisch)

- `pattern_key = "|".join(sorted(error_labels))` (leer → `__no_labels__`)
- Top‑Counts in `learn.error_patterns` (pro Run: Fenster wird ersetzt)
- **Losing conditions** (Top 10): Aggregation aus Signal/Feature‑Feldern für Trades mit `pnl_net_usdt < 0` — wird bei `GET /learning/patterns/top` live aus den Evaluations berechnet

## Empfehlungen (deterministisch)

| Regel                                                                                | Typ              | Inhalt                                                      |
| ------------------------------------------------------------------------------------ | ---------------- | ----------------------------------------------------------- |
| Viele Verluste mit `HIGH_TF_CONFLICT`                                                | `signal_weights` | Multi‑TF‑Gewicht / Gate                                     |
| Viele Verluste mit `STOP_TOO_TIGHT`                                                  | `risk_rules`     | `LEARN_STOP_MIN_ATR_MULT` erhöhen                           |
| `profit_factor < LEARNING_RETIRE_PF` (≥5 Trades)                                     | `retire`         | Vorschlag Retire — **keine** automatische Registry‑Änderung |
| `profit_factor ≥ LEARNING_PROMOTE_PF`, `max_drawdown ≤ LEARNING_MAX_DD` (≥10 Trades) | `promotion`      | Vorschlag Promotion — **keine** Autopromotion               |

Status in DB: `new` (manuell `approved` / `rejected` / `applied` vorgesehen).

## Promotion / Retire Gates (Schwellen)

| ENV                   | Default | Zweck                                       |
| --------------------- | ------- | ------------------------------------------- |
| `LEARNING_PROMOTE_PF` | 1.4     | Mindest‑Profit‑Factor für Promote‑Vorschlag |
| `LEARNING_RETIRE_PF`  | 0.9     | PF darunter → Retire‑Vorschlag              |
| `LEARNING_MAX_DD`     | 0.15    | Max. Drawdown für Promote‑Vorschlag         |

## Drift Detection

- `LEARNING_ENABLE_ADWIN=true`: vereinfachter **SimpleAdwin** (adaptives Fenster, Split‑Mittelwert‑Test) auf Zeitreihe `pnl_net_usdt` oder `win_rate` (`LEARNING_ADWIN_METRIC`) je Strategie und global.
- Bei erkanntem Drift (steigende Flanke): Eintrag in `learn.drift_events`.
- Vollständiges ADWIN nach Bifet & Gama (2007) mit formalen Guarantees — siehe Originalpaper; V1 ist bewusst vereinfacht aber nicht „Dummy“.

## MLflow (optional)

- `LEARNING_ENABLE_MLFLOW=true` und `MLFLOW_TRACKING_URI` setzen.
- Experiment `learning_engine_v1`: Params (Fenster, Schwellen), Metrics (aggregierte Kennzahlen pro Fenster), Artifact JSON‑Report.
- **Keine Secrets** loggen; in Produktion URI über Secret Manager (Hinweis).
- Dokumentation: [MLflow Tracking](https://www.mlflow.org/docs/latest/tracking.html)

## API

| Methode | Pfad                                        |
| ------- | ------------------------------------------- |
| GET     | `/learning/health`                          |
| GET     | `/learning/metrics/strategies?window=7d`    |
| GET     | `/learning/patterns/top?window=7d&limit=20` |
| GET     | `/learning/recommendations/recent?limit=50` |
| POST    | `/learning/run-now`                         |

## Seed / Workflow

```bash
python infra/migrate.py
python tools/seed_trade_evaluations.py
curl -s -X POST http://localhost:8090/learning/run-now
```

## Nächster Schritt

Prompt 24: Backtesting + Replay mit Purged/Embargo CV.
