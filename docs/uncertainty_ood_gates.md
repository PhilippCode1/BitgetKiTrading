# Unsicherheit, Kalibrierung und OOD als harte Gates

## Policy-Version

`uncertainty-gates-v1` (`signal_engine.uncertainty.UNCERTAINTY_POLICY_VERSION`).

## Kalibrierung

- Take-Trade-Modell: Produktionsartefakte tragen `calibration_method` (sigmoid/isotonic); wird in `take_trade_model_diagnostics.calibration_method` und auf dem Signal dupliziert.
- Ist `MODEL_CALIBRATION_REQUIRED=true` und es liegt eine `take_trade_prob` vor, aber **keine** Kalibrierungsmethode → **harte Abstinenz** (`take_trade_calibration_missing_when_required`).

## Uncertainty-Score (0..1)

Gewichtete Mischung aus Datenqualitaet, Regime-Unsicherheit, Modell-Konfidenz und max(Shadow-Divergenz, OOD-Score).

**Klassifikator-Unsicherheit:** Maximum aus (1 − Confidence) und **normalisierter Binaer-Entropie** der kalibrierten Wahrscheinlichkeit (Maximum bei p=0.5).

**Regressor:** Bound-Proximity der BPS-Projektionen (OOD-/Grenznaehe).

## OOD

- Feature-Robust-Z (Training-Referenz) pro Modell → `ood_score_0_1`, `ood_alert`, `ood_reasons_json`.
- **Harte Abstinenz** bei `ood_alert` oder wenn `ood_score >= MODEL_OOD_HARD_ABSTAIN_SCORE` (auch ohne Alert).

## Abstentions- und Lane-Regeln

| Situation                               | `trade_action` | `uncertainty_execution_lane` | `uncertainty_gate_phase` |
| --------------------------------------- | -------------- | ---------------------------- | ------------------------ |
| Harte Abstinenz (s. unten)              | `do_not_trade` | —                            | `blocked`                |
| Moderate Unsicherheit / OOD / Divergenz | `allow_trade`  | `shadow_only`                | `shadow_only`            |
| Leichte Unsicherheit                    | `allow_trade`  | `paper_only`                 | `minimal`                |
| Unter allen Paper-Schwellen             | `allow_trade`  | —                            | `full`                   |

**Harte Abstinenz**, wenn mindestens eines zutrifft:

- fehlende Kalibrierung bei Pflicht
- `model_ood_alert` oder `ood_score >= MODEL_OOD_HARD_ABSTAIN_SCORE`
- fehlende `take_trade_prob` oder unvollstaendige BPS-Projektion
- `uncertainty_score >= MODEL_MAX_UNCERTAINTY`
- `shadow_divergence >= MODEL_SHADOW_DIVERGENCE_HARD_ABSTAIN`

**Shadow-Lane** (mindestens eines): Uncertainty-, OOD- oder Divergenz-Schwellen ab `MODEL_UNCERTAINTY_SHADOW_LANE` / `MODEL_OOD_SHADOW_LANE_SCORE` / `MODEL_SHADOW_DIVERGENCE_SHADOW_LANE`.

**Paper-Lane** (wenn nicht Shadow): entsprechend `MODEL_UNCERTAINTY_PAPER_LANE` / `MODEL_OOD_PAPER_LANE_SCORE`.

## Zusammenspiel Risk, Regime, Meta

1. **Deterministisches Risk/Rejection** (Scores, News, Gates) kann vor Uncertainty bereits `do_not_trade` setzen; dann wird keine Uncertainty-Execution-Lane erzwungen (Merge bleibt konservativ).
2. **Regime** (z. B. Shock) erhoeht die Regime-Komponente im Uncertainty-Score und erscheint in `regime_uncertain`; Meta-Labeling (Prompt 22) nutzt zusaetzlich Stress-Regime fuer `shadow_only`.
3. **Meta-Lane** aus Hybrid: `merge_meta_trade_lanes(uncertainty_lane, hybrid_lane)` — **restriktivere** Lane gewinnt. Live nur bei `candidate_for_live` (Live-Broker).

## Explain- und Operator-Pfad

- `source_snapshot_json.uncertainty_gate`: Phase, Lane, Lane-Gruende.
- Event-Payload: `uncertainty_gate_phase`, `uncertainty_execution_lane`, `uncertainty_lane_reasons_json`, `meta_trade_lane` (gemerged), optional `meta_trade_lane_hybrid_raw`.
- `risk_warnings_json`: Codes `UNCERTAINTY_OR_OOD_BLOCK`, `UNCERTAINTY_SHADOW_LANE`, `UNCERTAINTY_MINIMAL_LANE`.
