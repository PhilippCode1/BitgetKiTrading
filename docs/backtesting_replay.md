# Backtesting & Replay (Prompt 24)

## Determinismus & Reproduzierbarkeit

Stabile Session-/Run-IDs, Seeds, Sortierung und protokollierte Manifeste (Modellkontrakt, Feature-Schema, Policy-Caps) sind in **[replay_determinism.md](./replay_determinism.md)** beschrieben. Shadow-vs-Live-Forensik: **[shadow_live_divergence.md](./shadow_live_divergence.md)**.

## Replay vs. Offline

| Modus                                                              | Zweck                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Replay** (`replay_to_bus`, `tools/replay/run_replay.py`)         | Historische `tsdb.candles` als `events:candle_close` (optional `market_tick`) in Redis; Speed-Faktor für schnelles Durchspulen. Laufende Downstream-Services können reagieren, aber Replay erzeugt **keine** Learning-Targets selbst. |
| **Offline-Backtest** (`offline`, `tools/backtest/run_backtest.py`) | Nutzt gespeicherte `learn.trade_evaluations` im Zeitraum; **ohne** Live-Pipeline. Fensteranker ist `decision_ts_ms`, Purging läuft über `decision_ts_ms -> closed_ts_ms`, Run in DB + `report.json` / `report.md`.                    |

## Walk-Forward vs. Purged K-Fold + Embargo

- **Walk-Forward**: Training nur aus Samples **vor** dem Test-Chunk (zeitlich kausal); Purge entfernt Label-Intervalle, die sich mit dem Testfenster überschneiden; **Embargo** entfernt Trainings-Labels, deren Ende unmittelbar vor `test_start` liegt (Anteil `BACKTEST_PURGED_EMBARGO_PCT` der Gesamtspanne).
- **Purged K-Fold + Embargo (V1)**: Deterministische K Blöcke über die sortierte Stichprobe; Training = alle Indizes außer Test, minus **Purged** (zeitliche Überlappung mit Testblock) und minus **Embargo** (nächste `embargo_pct * n` Indizes nach dem Testblock).

Klassisches i.i.d.-K-Fold ist für finanzielle Zeitreihen oft **biased** (Leakage). **Lopez de Prado** (_Advances in Financial Machine Learning_) beschreibt Purging und Embargo als Schutz vor Informationslecks durch überlappende Labels und serielle Korrelation.

## Konfiguration (ENV)

| Variable                      | Beispiel              | Zweck                            |
| ----------------------------- | --------------------- | -------------------------------- |
| `BACKTEST_ARTIFACTS_DIR`      | `artifacts/backtests` | Ausgabe (relativ zum Repo-Root)  |
| `BACKTEST_DEFAULT_CV`         | `walk_forward`        | Default für API                  |
| `BACKTEST_PURGED_EMBARGO_PCT` | `0.05`                | Embargo-Anteil                   |
| `BACKTEST_KFOLDS`             | `5`                   | Folds (2..20)                    |
| `REPLAY_SPEED_FACTOR`         | `60`                  | 60× schneller als Echtzeit-Delta |

## Target-Anker & Leakage

- Learning-Targets werden in `learn.trade_evaluations` am
  Entscheidungszeitpunkt verankert: `decision_ts_ms = analysis_ts_ms`, sonst
  `opened_ts_ms`.
- Offline-Backtests selektieren Samples über `decision_ts_ms` und purgen
  Intervalle `decision_ts_ms -> closed_ts_ms`, damit Pre-Trade-Kontext und
  Post-Trade-Labels kausal getrennt bleiben.
- `expected_return_gross_bps` beschreibt den Marktpfad, `expected_return_bps`
  denselben Trade **nach** Fees, Funding und Slippage. `expected_mae_bps`,
  `expected_mfe_bps` und `liquidation_proximity_bps` teilen denselben
  Zeitanker.
- Replay publiziert optional `market_tick` nur als Close-Proxy. Daraus allein
  duerfen keine kostenrealistischen Labels abgeleitet werden.

## Runs ausführen

```bash
# Offline
python tools/backtest/run_backtest.py --symbol <example_symbol> --from 1710000000000 --to 1710003600000 --cv walk_forward
python tools/backtest/run_backtest.py --symbol <example_symbol> --from 1710000000000 --to 1710003600000 --cv purged_kfold_embargo

# Replay (Redis + Postgres; deterministische session_id)
python tools/replay/run_replay.py --symbol <example_symbol> --from ... --to ... --tf 5m --speed 60

# API (kleiner Sync-Run, max. ~14 Tage Spanne)
curl -s -X POST http://localhost:8090/backtests/run-now \
  -H "Content-Type: application/json" \
  -d '{"from_ts_ms":1710000000000,"to_ts_ms":1710003600000,"cv_method":"walk_forward","symbol":"<example_symbol>"}'
```

## Artefakte & Sicherheit

- Pro Run: `artifacts/backtests/<run_id>/report.json` und `report.md`.
- **Keine Secrets** in Reports; in Produktion Artefakte besser in Object Storage (S3/GCS) mit Zugriffskontrolle.

## API

- `GET /backtests/runs?limit=20`
- `GET /backtests/runs/{run_id}` (inkl. Folds)
- `POST /backtests/run-now`

## Interpretation

- **metrics_json** (Run): aggregiert über alle Evaluations im Fenster (Profit Factor, Drawdown, Win-Rate, …).
- **metrics_json** enthält seit Prompt 15 auch `take_trade_rate`,
  `liquidation_risk_rate`, `avg_expected_return_bps`,
  `avg_expected_return_gross_bps`, `avg_expected_mae_bps` und
  `avg_expected_mfe_bps`.
- **Folds**: `test`-Metriken auf dem Out-of-Sample-Chunk; `train` nur zur Einordnung (kein Tuning in V1).
