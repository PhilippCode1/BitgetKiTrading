# Mehrdimensionale Prognoseschicht (Return, MAE, MFE)

## Zielgroessen (Labels → Modelle)

| Ausgabe               | Bedeutung                                                          | Training                                                                     |
| --------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `expected_return_bps` | Erwarteter Netto-Preis-Return im Horizont (Vorzeichen je Richtung) | `expected_return_bps`, Ziel-Skalierung `asinh` + Quantil-Clipping 0.5–99.5 % |
| `expected_mae_bps`    | Erwartete maximale **adverse** Bewegung (bps, nicht negativ)       | `expected_mae_bps`, `log1p` + Clip oben 99.5 %                               |
| `expected_mfe_bps`    | Erwartete maximale **guenstige** Exploration (bps)                 | `expected_mfe_bps`, wie MAE                                                  |

Feature-Vektor: `SIGNAL_MODEL_FEATURE_FIELDS` inkl. **Regime-One-Hots**, Spread, Execution/Volatility-Cost, Impact, Funding, Scores — Regime-Abhaengigkeit wird vom Booster mitgelernt; Evaluierung pro Regime in `regime_metrics` (MAE je `market_regime`).

## Robustheit (Training)

- **Quantil-Clipping** der Trainings-Labels vor Fit (Winsorizing).
- **BoundedRegressionModel**: Vorhersage auf trainierte Quantil-Grenzen begrenzt.
- **HistGradientBoostingRegressor** mit `loss="absolute_error"` (L1-artig, weniger empfindlich gegen Ausreisser als MSE).
- **Walk-forward / Purged-KFold** mit Embargo (Zeitreihen-Leakage).

## Inferenz: Kosten und Slippage

Modell liefert **Roh-Schaetzungen**; `shared_py.projection_adjustment.apply_projection_cost_adjustment` bildet **effektive** Groessen:

- **Roundtrip-Kosten (bps):** `execution_cost_bps` + `volatility_cost_bps` + beidseitig halbes `spread_bps`.
- **Netto-Return:** Roh-Return minus Roundtrip (Hybrid-Gates nutzen diese Werte in `app.signals_v1`).
- **Effektives adverse MAE:** Roh-MAE + Anteil von Impact + halbem Spread (Richtung: Buy-Impact bei Long, Sell bei Short).
- **Effektives MFE:** Roh-MFE abzueglich konservativer Exit-Slippage.
- **`safety_stop_buffer_bps`:** dokumentierter Puffer fuer Stop-Setups (MAE_eff × Faktor + halbes Spread), fuer Exit-Engine / Playbooks.

Rohwerte bleiben unter `target_projection_summary.model_raw_bps` bzw. in `target_projection_adjusted`.

## Liquidationsnaehe und Hebel

`liquidation_proximity_stress_0_1` vergleicht **effektives MAE** mit einer groben Safe-Room-Naeherung `(10000 / L) × 0.82` bps (kein exchange-spezifisches Maintenance — nur relatives Risiko).

`liquidation_proximity_cap` geht als zusaetzlicher Faktor in `factor_caps` des Integer-Hebel-Allocators ein und kann den Hebel bei hohem Stress senken, **bevor** die finale Positionsgroesse fixiert wird.

## Positionsgroesse und Exit (Downstream)

- **Hybrid / `trade_score`:** nutzen effektive `expected_*_bps`, projiziertes RR = MFE_eff / MAE_eff.
- **Hebel:** Edge- und RR-Scores plus Spread/Slippage/Funding/Depth-Caps; zusaetzlich Liquidations-Cap.
- **Live-Broker / Exit-Validation:** nutzt weiterhin Signal-Felder und erlaubten Hebel; `safety_stop_buffer_bps` kann als fachliche Mindest-Distanz zum Stop herangezogen werden (Integration im Exit-Service bei Bedarf).

## Evaluationsmetriken (Holdout + CV)

- `mae_bps`, `rmse_bps`, `median_absolute_error_bps`, optional `r2`.
- CV-Summary: `walk_forward_mean_mae_bps`, `purged_kfold_mean_mae_bps`.
- `regime_metrics`: MAE und Mittelwerte je Regime.
- `target_summary_train.skewness`: Schiefe der Trainings-Labels (Monitoring).
