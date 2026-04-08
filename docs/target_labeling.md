# Target-Konstruktion Modellkern (Prompt 20)

## Auswertefenster (Holding / Zeitachse)

| Grenze                 | Semantik                                                                                                                                                                                           |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `decision_ts_ms`       | Anker fuer Features und News (kein Leak aus der Zukunft vor diesem Zeitpunkt).                                                                                                                     |
| `opened_ts_ms`         | Beginn der ausgefuehrten Position; Liquidationsnaehe und Stop-Puffer werden ab hier auf dem Preispfad berechnet.                                                                                   |
| `evaluation_end_ts_ms` | **Ende des Label-Fensters** — bei Live-Evaluation = `closed_ts_ms`. Kerzen mit `start_ts_ms > evaluation_end_ts_ms` werden verworfen und im Audit als `candle_start_after_evaluation_end` geloggt. |

**Aggregation des Preispfads:** primaer 1m-Kerzen von `decision_ts_ms` bis `closed_ts_ms` (Fallback: Signal-Timeframe), siehe `process_trade_closed` in der Learning-Engine.

## Trade-Side

Alle Richtungs-Bps (`expected_return_*`, MAE/MFE, Slippage) sind **long/short-konform** ueber `_directional_move_bps`: fuer Long zaehlt Preisanstieg als positiver Move, fuer Short analog invertiert.

## Zielgroessen (fachlich)

| Ziel                                    | Definition                                                                                                                                                                                                                                                                    |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **take_trade_label**                    | Binaer: `expected_return_bps > 0` und **kein** `liquidation_risk`. Fasst „lohnender, nicht katastrophaler“ Trade fuer Meta-Classifier zusammen.                                                                                                                               |
| **expected_return_gross_bps**           | Markt-Rendite in bps vom **Entscheidungs-Referenzpreis** zum **Exit-Referenzpreis** (ohne explizite Fee/Funding-Zerlegung im Brutto-Pfad).                                                                                                                                    |
| **expected_return_bps**                 | **Netto**-Rendite in bps: `pnl_net_usdt / ( \|qty\| * entry_reference_price ) * 10000` — enthaelt Fees, Funding und realisierte Slippage gegenueber Referenz.                                                                                                                 |
| **expected_mfe_bps**                    | **Maximum Favorable Excursion** ab Entscheidungs-Referenz: bestes erreichtes Szenario innerhalb des **geclippten** Pfads `[decision_ts, evaluation_end]` anhand Kerzen-High/Low.                                                                                              |
| **expected_mae_bps**                    | **Maximum Adverse Excursion** (symmetrisch): groesster nachteilige Move in bps im selben Fenster.                                                                                                                                                                             |
| **liquidation_proximity_bps**           | Kleinstes positives Preis-Puffer-Mass zwischen **adverser Extremstelle nach Open** und approximierter **Liquidationspreis**-Schwelle (Isolated-Margin-Modell mit MMR und Fee-Puffer). `0` wenn Grenze erreicht oder ueberschritten; `None` wenn keine Approximation moeglich. |
| **liquidation_risk**                    | `true`, wenn Exchange-State `liquidated` **oder** approximierter Liquidationspuffer `<= 0`.                                                                                                                                                                                   |
| **policy_stop_proximity_bps** _(Audit)_ | Optional: Puffer zwischen schlimmster adverser Stelle und geplantem **Stop-Preis** aus `stop_plan_json` — Kategorie „unzulaessiges Risiko“ / Policy-Abstand, nicht identisch mit Exchange-Liquidation.                                                                        |

## Kostenannahmen

- **Netto-Return** nutzt echtes `pnl_net_usdt` (inkl. Fees, Funding).
- **Slippage-Felder** (`slippage_bps_entry` / `slippage_bps_exit`) messen unguenstige Abweichung Fill vs. Referenzpreis (Entry: Decision-Referenz, Exit: Exit-Referenz).
- **Brutto-Excursion** (MAE/MFE) ist bewusst **preis-basiert**, damit das Modell Markt-Stress sieht; Netto-Return traegt Ausfuehrungsrealismus.

## Leakage- und Konsistenz-Schutz

1. **Kerzen-Clip** (`clip_candles_to_evaluation_window`): keine Bars nach `evaluation_end_ts_ms`; keine Bars vor `decision_ts_ms` im Excursions-Pfad.
2. **Audit** `window_issues`: meldet u. a. `evaluation_end_before_decision` und zukuenftige Kerzen — sichtbar in `model_contract_json.target_labeling`.
3. **Referenzketten** getrennt dokumentiert im Audit (`reference_leg`), damit Training/Backtest dieselben Dehnungen nachvollziehen kann.

## Regime und Marktzustaende

Numerische Targets werden **nicht** automatisch skaliert. Stattdessen liefert `regime_target_stratification_hints(market_regime)` im Audit fachliche Hinweise (z. B. hoehere MAE/MFE-Varianz unter `shock`), damit Training stratifizierte Baselines, getrennte Kalibrierung oder Robust-Loss waehlen kann. `market_regime` stammt aus dem normalisierten Signal-Regime.

## Artefakt

Vollstaendiges Audit pro Trade: `model_contract_json.target_labeling` nach `build_model_contract_bundle(..., target_labeling_audit=...)`.

Siehe auch `docs/learning_feedback.md` (Pipeline-Kontext).
