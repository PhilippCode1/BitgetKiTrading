# Learning-Engine: Trainingspipeline (Prompt 28)

## Einheitlicher Pfad

| Schicht                    | Ort                                                                                             |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| **CLI**                    | `python -m learning_engine.training <take-trade\|expected-bps\|regime\|specialists-audit\|all>` |
| **Orchestrierung**         | `learning_engine.training.pipeline.run_training_jobs` (von CLI und intern nutzbar)              |
| **Feature-Load & Dataset** | jeweiliger Trainer (`repo_model_runs` → Builder z. B. `build_take_trade_training_dataset`)      |
| **Splits / CV**            | `training/cv_runner.py` (Walk-Forward + Purged K-Fold mit Embargo)                              |
| **Kalibrierung**           | `take_trade_prob` (Sigmoid/Isotonic auf Holdout-Calibration-Split)                              |
| **Evaluierung**            | Test-Holdout-Metriken + `cv_report.json`                                                        |
| **Artefakte**              | Unter `MODEL_ARTIFACTS_DIR` bzw. modellspezifische `*_ARTIFACTS_DIR`                            |

CLI-Optionen:

- `--symbol <example_symbol>` — Datenfilter
- `--no-promote` — kein `promoted_bool` in der Registry
- `--summary-out path.json` — kompaktes JSON mit `results` pro Teiljob (Run-IDs, Pfade aus Trainer-Return)

HTTP bleibt parallel (`POST /learning/models/.../train-now`); dieselben Trainer-Funktionen.

**E2E-Lernsubstrat:** `learn.e2e_decision_records` (siehe `docs/learning_e2e_decision_records.md`) speichert pro Signal den Entscheidungs-Snapshot (Spezialisten, Router, Stops, Kontext) und Outcomes; Trainer/Dataset-Builder können darüber joinen (`signal_id`, `trade_evaluation_id`), ohne die bestehenden `trade_evaluations`-Pfad zu ersetzen.

## Run-Manifest (`run_manifest.json`)

Pro Lauf schreibt jeder Trainer neben `training_manifest.json` ein **`run_manifest.json`** (Version `run_manifest_version`).

Enthalten u. a.:

- `training_pipeline_version` (Konstante `TRAINING_PIPELINE_VERSION`, aktuell **1.2.0**)
- `run_id`, `model_name`, `model_version`, `trained_at_ms`
- **Datensatz:** `data_version_hash`, `dataset_hash`, `training_window`, `symbol`, `row_counts`
- **Feature-Schema:** `schema_hash`, `target_schema_hash`, vollstaendiger `contract`
- **Splits & Eval:** eingebettetes `training_manifest` (CV-Parameter), `split_description`, `cv_report_summary`
- **Kalibrierung:** `method`, `applied`
- **Metriken:** Test-Metriken (modellabhaengig)
- **Parameter:** Snapshot relevanter `LearningEngineSettings` (CV, Seeds, Mindestzeilen, Artefakt-Pfade)
- **Artefakte:** Repo-relative und absolute Pfade aller Dateien inkl. `run_manifest.json`
- **Reproduzierbarkeit:** Python-/Sklearn-/NumPy-Versionen, `PYTHONHASHSEED`, Git-HEAD oder `LEARNING_CODE_REVISION`, `learning_engine_source_bundle_sha256_40`

Zusaetzlich unveraendert: `metadata.json`, `cv_report.json`, `model.joblib`, ggf. `calibration.joblib`.

## CV-Audit: Symbol-Leakage und Marktfamilie pro Fold (ab 1.2.0)

`cv_report.json` enthaelt pro Walk-Forward- und Purged-KFold-Fold zusaetzlich:

- `symbol_leakage` (`strict_symbol_overlap`, gemeinsame Symbole in Train/Test — bei Multi-Symbol-Pools pruefen)
- `market_family_train_counts` / `market_family_test_counts`

Die `summary`-Sektion enthaelt `symbol_leakage_walk_forward` und `symbol_leakage_purged_kfold_embargo` (Aggregat).

Trainer `take_trade_prob`, `expected_bps` (alle Koepfe), `market_regime_classifier` nutzen dieselbe Anreicherung; Trainingsbeispiele tragen `symbol`, `market_family`, `error_labels` fuer konsistente Audits.

## Trade-Relevanz-Report (Take-Trade)

Nach Holdout-Test schreibt `take_trade_prob` **`trade_relevance_report.json`**: Abstention-/High-Conf-Tail-Kennzahlen, `stop_failure_mode_counts_test` (aus `error_labels`), `execution_sensitivity` (Korrelation Prob vs. `execution_cost_bps`, falls genug Daten). Kompakte Kennzahlen liegen in `metadata.trade_relevance_summary` und in `metrics_json.trade_relevance_summary` der Registry-Zeile.

## Spezialisten-Readiness (ohne Training)

- **CLI:** `python -m learning_engine.training specialists-audit [--symbol …]`
- **HTTP:** `GET /learning/training/specialists-readiness?symbol=…` (read-only)

Nutzt `SPECIALIST_FAMILY_MIN_ROWS` (Default 40): Familien unterhalb werden als `degrade_to_pooled_model` markiert.

## Reproduzierbarkeit

1. **Deterministische Daten:** gleiche `learn.trade_evaluations`-Zeilen + gleicher `symbol`-Filter → gleiche `dataset_hash` / `data_version_hash` (siehe `compute_data_version_hash`).
2. **Seed:** `TRAIN_RANDOM_STATE` (Default 42) steuert sklearn-HGB und Kalibrierer.
3. **Hash-Randomisierung:** optional `PYTHONHASHSEED=0` setzen.
4. **Code-Stand:** `LEARNING_CODE_REVISION=<sha>` in CI setzen, falls kein `.git` vorhanden; sonst wird `git rev-parse HEAD` versucht.
5. **Quellbaum-Fingerprint:** `learning_engine_source_bundle_sha256_40` aendert sich bei jeder Aenderung unter `learning_engine/*.py`.

Hinweis: kleine numerische Unterschiede durch BLAS-Threading sind moeglich; fuer strikte Bit-Identitaet gleiche CPU/OS/Thread-Limits verwenden.

## Runs starten, validieren, registrieren

1. **Start:** CLI wie oben oder HTTP `train-now` mit `promote=true|false`.
2. **Validierung:** `run_manifest.json` pruefen (`metrics`, `cv_report_summary`, `row_counts`); Promotion-Gates optional ueber `analytics/promotion_gates.py` / Registry-V2.
3. **Registrierung:** erfolgt automatisch durch `repo_model_runs.insert_model_run` bei jedem Trainer; Champion-Flags ueber `promote` und ggf. Registry-V2-Routen.

## Smoke-Kommando

```bash
export DATABASE_URL=postgresql://...
export REDIS_URL=redis://...
export TAKE_TRADE_MODEL_ARTIFACTS_DIR=/tmp/le_tt
python -m learning_engine.training take-trade --no-promote --summary-out /tmp/train_summary.json
```

(Voraussetzung: ausreichend Zeilen in `learn.trade_evaluations`, sonst Trainer wirft erwartungsgemaess.)
