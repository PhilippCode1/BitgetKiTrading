# learning-engine

Trade-Feedback-Collector (Prompt 21): konsumiert Redis-Streams (`signal_created`, `trade_opened`, `trade_closed`, …), schreibt `learn.trade_evaluations` und **`learn.e2e_decision_records`** (E2E-Lernschema inkl. Spezialisten-Snapshot, Outcomes, QC-Labels). Siehe `docs/learning_e2e_decision_records.md`.

## Lokal

```bash
export DATABASE_URL=postgresql://...
export REDIS_URL=redis://localhost:6379
pip install -e ".[dev]"
python -m learning_engine.main
```

## API

- `GET /health`
- `GET /learning/e2e/recent?limit=50` — E2E-Lernrecords
- `GET /learning/trades/recent?limit=50`
- `GET /learning/trades/{paper_trade_id}`
- `GET /learning/summary?window_days=7`
- `GET /learning/models/take-trade/latest`
- `GET /learning/models/take-trade/runs?limit=20`
- `POST /learning/models/take-trade/train-now?symbol=<example_symbol>&promote=true`
- `GET /learning/models/expected-bps/latest`
- `GET /learning/models/expected-bps/runs?limit=20`
- `POST /learning/models/expected-bps/train-now?symbol=<example_symbol>&promote=true`
- `GET /learning/models/regime-classifier/latest`
- `GET /learning/models/regime-classifier/runs?limit=20`
- `POST /learning/models/regime-classifier/train-now?symbol=<example_symbol>&promote=true`

## Trainingspipeline (reproduzierbar)

- Zentraler Artefakt-Wurzelpfad: `MODEL_ARTIFACTS_DIR` (Default `artifacts/models`).
  Wenn `TAKE_TRADE_MODEL_ARTIFACTS_DIR`, `EXPECTED_BPS_MODEL_ARTIFACTS_DIR` oder
  `REGIME_CLASSIFIER_MODEL_ARTIFACTS_DIR` nicht gesetzt sind, werden Unterordner
  `take_trade_prob/`, `expected_bps/` bzw. `regime_classifier/` darunter verwendet.
- CLI (gleiche Trainer wie HTTP): `python -m learning_engine.training <take-trade|expected-bps|regime|all>`
  (Optionen `--symbol`, `--no-promote`, `--summary-out pfad.json`). Orchestrierung:
  `learning_engine.training.pipeline.run_training_jobs`. Dokumentation:
  [docs/learning_engine_training_pipeline.md](../docs/learning_engine_training_pipeline.md).
- Pro Lauf werden geschrieben: `model.joblib`, `metadata.json`, `training_manifest.json`,
  **`run_manifest.json`** (vollstaendiges Run-Manifest: Schema, Code-Fingerprint, Parameter,
  Metriken, Artefakt-Pfade, Repro-Metadaten), `cv_report.json` (Walk-Forward **und**
  Purged-K-Fold mit Embargo).
- `take_trade_prob`: zusaetzlich `calibration.joblib` (Kalibrierer separat zum Audit).
- Regime-Modell (`market_regime_classifier`): Multiclass-HGB auf Featurevektor **ohne**
  `market_regime_is_*`-One-Hots (eigenes Schema `regime_model_feature_vector`), Ziel ist
  die normalisierte Spalte `market_regime` aus den Evaluations.
- Inferenz-Helfer (reines Laden): `learning_engine.inference.artifacts.load_joblib_artifact`.
- `learning_engine.backtest` exportiert `build_backtests_router` erst bei Zugriff
  (lazy), damit Trainingscode keine schwere Router-Kette importiert.

## Modellvertrag / Data Quality

- `learn.trade_evaluations.model_contract_json` speichert seit Prompt 13 die
  Shared-Vertragsmetadaten fuer Feature-Snapshots, Signal-Outputs und Targets.
- `feature_snapshot_json` nutzt denselben Feature-Vertrag wie die Signal-Engine
  und enthaelt alle Modell-Timeframes statt eines losen Teil-Snapshots.
- `LEARN_MAX_FEATURE_AGE_MS` gate't veraltete Features beim Aufbau des
  Learning-Snapshots.
- Prompt 14 erweitert den Snapshot um Cost-/Liquidity-Felder wie
  `execution_cost_bps`, `volatility_cost_bps`, `funding_rate_bps`,
  `open_interest_change_pct` sowie `*_age_ms`- und `*_source`-Metadaten.
- Learning markiert fehlende oder nur per Ticker approximierte Liquidity-Daten
  explizit (`missing_liquidity_feature_snapshot`,
  `liquidity_feature_snapshot_fallback`) statt sie als neutrale Features zu
  behandeln.
- Prompt 15 erweitert die persistierten Targets um
  `take_trade_label`, `expected_return_bps`,
  `expected_return_gross_bps`, `expected_mae_bps`, `expected_mfe_bps`,
  `liquidation_proximity_bps` und `liquidation_risk`.
- Target-Anker ist `decision_ts_ms` (`analysis_ts_ms` des Signals, sonst
  `opened_ts_ms`). Feature-/News-Snapshots bleiben pre-trade; Return-/MAE-/MFE-
  und Liquidations-Labels werden nur aus nachgelagerten Candle-/Fill-/Fee-/
  Funding-Daten bis `closed_ts_ms` berechnet.
- Prompt 16 fuehrt eine kanonische Signal-Regime-Sicht in
  `signal_snapshot_json` ein: `market_regime`, `regime_bias`,
  `regime_confidence_0_1`, `regime_reasons_json`.
- `learn.trade_evaluations.market_regime` wird dabei aus dem Signal-Regime
  normalisiert statt aus rohem `structure_state.trend_dir`, damit Audit,
  Learning und Backtests dieselbe Taxonomie verwenden.
- Empfehlungen koennen damit jetzt auch verlusttraechtige
  Cost-/Liquidity-Regime erkennen und strengere Execution-Gates vorschlagen.
- Prompt 17 trainiert darauf aufbauend ein tabellarisches Baseline-Modell fuer
  `take_trade_prob`: `HistGradientBoostingClassifier` plus explizite Kalibrierung
  (`sigmoid` oder `isotonic`) auf einem separaten chronologischen
  Kalibrierungsfenster.
- Trainingsdaten kommen ausschliesslich aus `learn.trade_evaluations`
  (`signal_snapshot_json` + `feature_snapshot_json` + `take_trade_label`); damit
  bleibt die Feature-/Label-Semantik zwischen Training und Inferenz identisch
  und leakage-sicher.
- Modellartefakte landen unter `TAKE_TRADE_MODEL_ARTIFACTS_DIR`, Metadaten und
  Promotions in `app.model_runs`. `metrics_json` und `metadata_json` enthalten
  Holdout-Metriken, Regime-Segmente und die Kalibrierungskurve fuer Audit.
- Prompt 18 trainiert darauf aufbauend drei getrennte Regressionsmodelle fuer
  `expected_return_bps`, `expected_mae_bps` und `expected_mfe_bps`.
- Basis-Estimator ist jeweils `HistGradientBoostingRegressor`; fuer stabile
  Risk-/Leverage-Nutzung werden die Targets ueber `asinh_clip`
  (`expected_return_bps`) bzw. `log1p_clip` (`expected_mae_bps`,
  `expected_mfe_bps`) skaliert und auf train-basierte Bounds begrenzt.
- Artefakte dieser Regressoren landen unter `EXPECTED_BPS_MODEL_ARTIFACTS_DIR`;
  `app.model_runs` speichert pro Zielmodell Version, Dataset-Hash, Holdout-
  Metriken und die verwendete Scaling-Methode.
- Prompt 19 erweitert `metadata_json` der Modell-Runs um eine train-basierte
  `feature_reference` (robuste Quantile/IQR je numerischem Feature) sowie
  `regime_counts_train`, damit die Signal-Engine OOD-Checks und
  Unsicherheits-Gates auf denselben Trainingsreferenzen aufbauen kann.
- Prompt 24 vereinheitlicht die Trainingspfade: Walk-Forward und Purged-K-Fold
  mit Embargo sind fester Bestandteil der Trainingslogik; `TRAIN_CV_KFOLDS`,
  `TRAIN_CV_EMBARGO_PCT` und `TRAIN_RANDOM_STATE` steuern Reproduzierbarkeit.
- Prompt 26: Online-Drift-Evaluator schreibt `learn.drift_events` (`drift_class=online`) und
  `learn.online_drift_state`; API `GET/POST /learning/drift/online-state|evaluate-now`.
  `ENABLE_ONLINE_DRIFT_BLOCK` koppelt Signal-Engine und Live-Broker an `warn` / `shadow_only` /
  `hard_block`. Siehe `docs/online_drift.md`.
- Prompt 25/29: Champion/Challenger-Registry (`app.model_registry_v2` + Historie/Checkpoint
  Migration `410`), API `GET /learning/registry/v2/slots`,
  `POST .../champion|challenger|stable-checkpoint|rollback-stable`,
  `DELETE .../champion|challenger`. Harte Promotions-Gates (`MODEL_PROMOTION_GATES_ENABLED`),
  optional Auto-Rollback bei Drift-`hard_block`. Governance: `docs/model_lifecycle_governance.md`,
  Registry-Uebersicht: `docs/model_registry_v2.md`.

Siehe `docs/learning_feedback.md`.
