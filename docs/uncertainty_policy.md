# Unsicherheits-Policy (Signal-Engine)

**Version:** `uncertainty-gates-v2` (`UNCERTAINTY_POLICY_VERSION` in `signal_engine/uncertainty.py`).

## Mehrdimensionale Komponenten (0..1)

| Komponente    | Bedeutung                                                                                   | Hauptinputs                                                                         |
| ------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **data**      | Datenlage, Staleness, Vollstaendigkeit, `feature_quality_status`                            | `ctx.data_issues`, `primary_feature.*`, Alter `computed_ts_ms` vs. `analysis_ts_ms` |
| **regime**    | Regime- und Uebergangsunsicherheit                                                          | `regime_state`, `regime_transition_state`, `regime_confidence_0_1`, `market_regime` |
| **execution** | Spread, Kosten, Tiefe, Orderbuch-Kontext                                                    | `spread_bps`, `execution_cost_bps`, `depth_to_bar_volume_ratio`, `orderbook_age_ms` |
| **model**     | Klassifikator-Entropy/Margin, Regressor-Bounds, strukturelle Divergenz Heuristik vs. Modell | Take-Trade-Diagnostik, Target-Projektion, `shadow_divergence`                       |
| **policy**    | Kalibrierpflicht, schwache Kalibrier-Tags                                                   | `MODEL_CALIBRATION_REQUIRED`, `take_trade_calibration_method`                       |

Der persistierte Skalar **`model_uncertainty_0_1`** ist ein **konservativer Aggregat** (gewichteter Mittelwert + Max-Komponenten-Boost), damit einzelne Risikodimensionen nicht weggemittelt werden.

## Harte Abstinenz (no_trade)

Zusaetzlich zu den bestehenden Regeln (OOD-Alert, fehlende Projektion, Kalibrierpflicht, …):

- **Stale Features:** `analysis_ts_ms - computed_ts_ms > SIGNAL_MAX_DATA_AGE_MS` → `feature_stale_hard_abstain`
- **Extreme Mikrostruktur:** Spread/Execution klar ueber konfigurierten Maxima → `execution_microstructure_hard_abstain`

## Ausfuehrungs-Lanes (shadow / paper)

Shadow-Lane kann ausgeloest werden durch: Aggregat-, OOD-, Shadow-Divergenz-Schwellen **oder** erhoehte **Execution-** bzw. **Daten**-Komponente (siehe `lane_reasons`).

## Kopplung an Leverage

`uncertainty_effective_for_leverage_0_1` = Aggregat plus zusaetzlicher Anteil aus Execution/Daten. In `hybrid_decision` fliesst dieser Wert in **`uncertainty_factor_cap`** (nur Hebel-Zweig), ohne den reinen Hybrid-`trade_score` kuenstlich zu verdoppeln.

## Exit-Bias (kein starres TP)

Bei hoher Execution-Unsicherheit: `exit_execution_bias = prefer_wider_stops_and_softer_targets`.  
Bei hoher Datenunsicherheit: `prefer_time_and_scale_out`.  
Gruende erscheinen in `uncertainty_reasons_json` und im Explain-Abschnitt **Mehrdimensionale Unsicherheit**.

## Monitoring-Hooks (`uncertainty_assessment.monitoring_hooks`)

| Flag                               | Semantik                                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------------------------ |
| `false_confidence_risk`            | Hohe Modellkonfidenz bei gleichzeitig hoher struktureller Divergenz (Heuristik vs. Kalibrierung) |
| `missing_calibrator_when_required` | Kalibrierpflicht verletzt                                                                        |
| `ood_fallback_only_no_alert`       | Erhoehtes OOD ohne Alert (Review-Kandidat)                                                       |

## Artefakte

- `app.signals_v1.uncertainty_effective_for_leverage_0_1` (persistiert; Migration `510_uncertainty_effective_leverage.sql`)
- `source_snapshot_json.uncertainty_assessment` (voll inkl. `components_v2`, `monitoring_hooks`)
- `reasons_json.uncertainty_components`, `reasons_json.uncertainty_exit_execution_bias`
- Explain: `sections.uncertainty_breakdown`
- Events: `uncertainty_effective_for_leverage_0_1` im Payload
- Entscheidungsgraph: Phase `uncertainty_ood` mit `components_v2` in `evidence`

## Tests

- `tests/signal_engine/test_uncertainty_policy.py` — Gates, Stale-Feature, Monitoring-Hook, Execution-Lane
