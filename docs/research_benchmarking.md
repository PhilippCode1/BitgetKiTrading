# Research: Benchmark-Harness und Evidenzpfad

Ziel: Policy- und Modellverbesserungen an **messbare Vergleiche** binden (Baselines, Lanes, Counterfactual-Spezifikationen), nicht an Erzählungen. **Kein LLM-Trading** — die Reports aggregieren nur gespeicherte `learn.trade_evaluations` und `learn.e2e_decision_records`.

## Komponenten (Learning-Engine)

| Teil            | Modul                                        | Zweck                                                                                                                                       |
| --------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Baselines       | `learning_engine.research.baseline_policies` | `always_no_trade`, Momentum, Mean-Reversion-RSI, konservative Qualität, Playbook-Familien-Proxy                                             |
| Metriken        | `learning_engine.research.benchmark_metrics` | Abstention-Qualität, high-confidence-FP-Rate, Stop-/Slippage-Label-Proxys, Drawdown-Teilsequenz, Korrelation PnL vs. `execution_cost_bps`   |
| Counterfactuals | `learning_engine.research.counterfactual`    | Strukturierte Szenarien aus E2E-Snapshots (alternativer Playbook-Kandidat, halber Hebel, Exit-Platzhalter, no-trade) — **keine Ausführung** |
| Harness         | `learning_engine.research.harness`           | JSON-Report inkl. Sortierung, `determinism`-Block, Slices nach `model_contract_json.feature_schema_version`                                 |

## CLI (Operator / CI mit DB)

```bash
python tools/research/run_benchmark_report.py
python tools/research/run_benchmark_report.py --symbol <example_symbol> --limit-eval 800 --limit-e2e 300
python tools/research/run_benchmark_report.py --stdout-json
```

Ausgabe: `RESEARCH_BENCHMARK_ARTIFACTS_DIR` (Standard `artifacts/research`) — `benchmark_evidence_*.{json,md}`.

## HTTP (read-only)

- `GET /learning/research/benchmark-evidence`
- Query: `symbol`, `limit_evaluations`, `limit_e2e`, `format=json|markdown`
- Wenn `RESEARCH_BENCHMARK_READ_SECRET` gesetzt ist: Header `X-Research-Benchmark-Secret` erforderlich (kein öffentliches Leaken aggregierter Betriebsdaten).

## Interpretation

- **`take_trade_label`** ist das **ex-post Lernziel** aus abgeschlossenen Evaluations; der „System“-Arm im Report nutzt dasselbe Label als Proxy für den **Vergleich mit Baselines**, nicht als Live-Gate-Output.
- **Paper / Shadow / Live** werden über `summarize_lane_outcomes` in Stichproben **gegenübergestellt** (geschlossene `pnl_net_usdt` je Lane), sobald `outcomes_json` befüllt ist.
- **Frühere „Systemversionen“** im Sinne von Feature-Pipeline: Report-Feld `by_model_contract_feature_schema_version` gruppiert nach `model_contract_json` (min. Zeilen pro Slice konfigurierbar im Harness-Parameter `min_rows_model_contract_slice`, Standard 20).

## Determinismus

Siehe Ergänzung in [replay_determinism.md](./replay_determinism.md) — der Report selbst listet Grenzen unter `determinism` (Wall-Clock, Float-Toleranz `FLOAT_METRICS_RTOL`).

## Tests

`pytest tests/learning_engine/test_research_harness.py` — reine Zeilen-Fixtures, keine DB.
