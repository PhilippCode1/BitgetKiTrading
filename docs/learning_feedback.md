# Learning Feedback Collector (Prompt 21)

## Event-Quellen

| Stream                                                                                          | Rolle                                                                                             |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `events:trade_closed`                                                                           | **Trigger**: vollständige Trade-Evaluation + DB-Upsert                                            |
| `events:trade_opened`, `events:trade_updated`, `events:signal_created`                          | Konsumiert (Consumer Group), nur `learn.processed_events` — Kontext kommt beim Close aus Postgres |
| `events:news_scored`, `events:structure_updated`, `events:drawing_updated`, `events:risk_alert` | Optional (`LEARN_CONSUME_OPTIONAL_STREAMS`), gleiches Muster                                      |

## Idempotenz

1. **Redis Consumer Group**: jede Consumer-Gruppe liefert Pending-Liste pro Consumer.
2. **`learn.processed_events (stream, message_id)`**: vor/nach Verarbeitung — bei erneutem Delivery mit gleicher `message_id` → Log `idempotent skip`, sofort `XACK`.

`trade_closed`-Pipeline: Evaluation-Insert und `mark_processed` in **einer** DB-Transaktion (`ON CONFLICT (paper_trade_id)`).

## Label-Regeln (V1)

Konfiguration über ENV (`LEARN_STOP_MIN_ATR_MULT`, `LEARN_FALSE_BREAKOUT_WINDOW_MS`, `LEARN_MULTI_TF_THRESHOLD`, `LEARN_STALE_SIGNAL_MS`, `LEARN_MAX_FEATURE_AGE_MS`).

| Code               | Bedingung                                                             |
| ------------------ | --------------------------------------------------------------------- |
| `STOP_TOO_TIGHT`   | `stop_distance_atr_mult` &lt; Schwellwert                             |
| `FALSE_BREAKOUT`   | `FALSE_BREAKOUT`-Structure-Event im Fenster nach Open                 |
| `HIGH_TF_CONFLICT` | Multi-TF-Score niedrig **oder** 4h-Feature `trend_dir` gegen Position |
| `NEWS_SHOCK`       | `paper.strategy_events` Typ `NEWS_SHOCK` für `position_id`            |
| `STALE_DATA`       | `analysis_ts_ms` des Signals zu alt vs. Open                          |

## Target-Labels (Prompt 15)

**Leakage-Anker**

- `decision_ts_ms = app.signals_v1.analysis_ts_ms`, Fallback `opened_ts_ms`
- Feature-/News-Kontext für Training wird nur bis `decision_ts_ms` gelesen
- Target-Pfad beginnt erst nach dem Entscheidungsanker; MAE/MFE und
  Referenzpreise nutzen nur vollständige Candle-Intervalle bis `closed_ts_ms`

| Feld                        | Bedeutung                                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------- |
| `take_trade_label`          | `true`, wenn `expected_return_bps > 0` **und** kein `liquidation_risk` vorliegt                   |
| `expected_return_gross_bps` | Richtungsadjustierte Marktbewegung von Entscheidungs-Referenzpreis bis Exit-Referenzpreis in bps  |
| `expected_return_bps`       | Reale Netto-Rendite in bps: `pnl_net_usdt / (qty_base * decision_reference_price) * 10000`        |
| `expected_mae_bps`          | Maximale adverse Excursion relativ zum Entscheidungs-Referenzpreis                                |
| `expected_mfe_bps`          | Maximale favourable Excursion relativ zum Entscheidungs-Referenzpreis                             |
| `liquidation_proximity_bps` | Kleinster Puffer zwischen adverser Post-Open-Preisbahn und approximierter Liquidationsschwelle    |
| `liquidation_risk`          | `true`, wenn Position liquidiert wurde oder der approximierte Liquidationspuffer auf `<= 0` fällt |

Auswertefenster, Stop-Puffer-Audit und Regime-Hinweise: siehe [target_labeling.md](target_labeling.md) (Prompt 20).

**Kostenrealismus**

- `expected_return_gross_bps` ist bewusst **brutto** (Marktpfad).
- `expected_return_bps` ist bewusst **netto** und enthält reale
  `fees_total_usdt`, `funding_total_usdt` sowie Entry-/Exit-Slippage.
- `slippage_bps_entry` und `slippage_bps_exit` messen seit Prompt 15 gegen
  Entscheidungs- bzw. Exit-Referenzpreise statt gegen bereits ausgeführte
  Fill-Mittelwerte.

## Schema

- `learn.trade_evaluations` — eine Zeile pro `paper_trade_id` (Position)
- `learn.signal_outcomes` — Aggregation pro `signal_id`
- `learn.processed_events` — Stream-Dedupe
- `learn.trade_evaluations.model_contract_json` — Shared-Vertrag fuer
  Feature-Snapshots, Signal-Outputs, Targets und Quality-Gate-Ergebnis

Migrationen: `140_learning_feedback.sql`, Contract-Erweiterung `300_model_contracts.sql`,
Target-Erweiterung `320_learning_target_labels.sql`.

Seit Prompt 13 wird `feature_snapshot_json` als kanonischer Multi-Timeframe-
Snapshot aus `shared_py.model_contracts` gespeichert; dadurch koennen
Training/Analytics und Signal-Inferenz nicht mehr stillschweigend verschiedene
Feature-Sets verwenden.

Seit Prompt 14 enthaelt derselbe Snapshot auch Cost-/Liquidity-Felder
(`execution_cost_bps`, `volatility_cost_bps`, `funding_rate_bps`,
`open_interest_change_pct`, `*_age_ms`, `*_source`). Fehlende oder nur per
Ticker approximierte Liquidity-Kontexte werden im Learning-Gate explizit
markiert statt implizit neutralisiert.

Seit Prompt 15 traegt `learn.trade_evaluations` zusaetzlich einen
Entscheidungsanker (`decision_ts_ms`) und explizite Return-/Excursion-/
Liquidations-Targets. Offline-Backtests und Trainingssplits purgen damit
Intervalle `decision_ts_ms -> closed_ts_ms`, nicht nur `opened_ts_ms -> closed_ts_ms`.

Seit Prompt 16 wird `market_regime` im Learning-Pfad aus dem kanonischen
Signal-Regime normalisiert (`trend|chop|compression|breakout|shock`) statt aus
rohen Strukturwerten wie `UP|DOWN|RANGE`. Die reichere Regime-Sicht
(`regime_bias`, `regime_confidence_0_1`, `regime_reasons_json`) liegt in
`signal_snapshot_json` und bleibt damit fuer Audit, Pattern-Analyse und
Training verfuegbar.

## Trainingspipeline und Artefakte (Prompt 24)

- Artefakt-Wurzel: `MODEL_ARTIFACTS_DIR`; pro Lauf entstehen u.a. `training_manifest.json`
  (Pipeline-Version, `data_version_hash`, Feature-/Target-Schema-Hashes, CV-Parameter,
  Entscheidungszeitfenster), `cv_report.json` mit **Walk-Forward** und **Purged-K-Fold
  inkl. Embargo**, sowie Modell- und (bei `take_trade_prob`) separates
  `calibration.joblib`.
- Reproduzierbarer CLI-Einstieg: `python -m learning_engine.training …` (siehe
  `services/learning-engine/README.md`).
- Zusaetzlich zu `take_trade_prob` und den drei Erwartungswert-Regressoren gibt es
  einen trainierbaren **Regime-Klassifikator** (`market_regime_classifier`) mit
  eigenem Feature-Schema ohne `market_regime_is_*`-Leakage.

## Fixture

```bash
python tools/publish_trade_closed_fixture.py
```

`FIXTURE_POSITION_ID` muss eine **existierende, geschlossene** `paper.positions.position_id` sein, sonst schreibt der Collector nichts Sinnvolles.
