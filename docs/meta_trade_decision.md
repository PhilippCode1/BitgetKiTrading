# Meta-Entscheidung (`take_trade_prob`) und Safety-Layer

## Reihenfolge

1. **Deterministischer Safety-Layer (vor Hybrid)**  
   Rejection-State, Uncertainty-Abstinenz, Datenqualitaet und feste Policy-Grenzen setzen `decision_state` / `trade_action` / `abstention_reasons_json`, bevor das Meta-Modell gewertet wird.

2. **Hybrid-Policy `hybrid-v4`** (`signal_engine.hybrid_decision`, inkl. Risk-Governor)  
   Nutzt u. a. kalibrierte `take_trade_prob`, erwartete Bps, projiziertes RR, Regime-Alignment und Hebel-Allocator.  
   **Wahrscheinlichkeits-Schutz:** `shrink_calibrated_take_trade_probability` zieht extreme `take_trade_prob` bei OOD-Score/Alert und hoher Modell-Unsicherheit zu 0,5 (Inferenz-Konservativismus; trainierte Kalibrierung bleibt im Artefakt).

3. **Meta-Lane** (`shared_py.meta_trade_decision.resolve_meta_trade_lane`)  
   Ordnet bei fachlich erlaubtem Hybrid eine Ausfuehrungsstufe zu, ohne den Safety-Layer zu ersetzen:
   - `do_not_trade`: Hybrid blockiert oder Safety/Modell bereits blockiert.
   - `shadow_only`: Stress-Regime (`shock`, `dislocation`), OOD-Alert oder fehlgeschlagener Feature-Quality-Gate → **Ausfuehrung wird auf `do_not_trade` gedrosselt** (nur Shadow/Analyse).
   - `paper_only`: moderate Edge/Unsicherheit/Kosten oder schwache Risk-/History-/Structure-Scores (Schwellen via `META_LANE_PAPER_*`).
   - `candidate_for_live`: strenge Kombination aus adjustierter Prob, Ueberzeugung und Struktur-/Risiko-Kontext.

## Zusammenspiel Live-Broker

Der **Live-Broker** prueft bei `effective_mode == "live"` zusaetzlich:  
`meta_trade_lane` muss `candidate_for_live` sein (oder fehlen/leer fuer aeltere Events ohne Feld).  
Sonst: `blocked` / `meta_trade_lane_not_live_candidate`.  
Risk-Engine und `trade_action == do_not_trade` bleiben die erste Barriere; die Meta-Lane ist die zweite, explizite Live-Grenze fuer **Paper-only**-Signale.

## Kalibrierung und Metriken

- **Training:** Kalibrierung des Take-Trade-Modells (z. B. Platt/Isotonic) liegt in `app.model_runs` (`calibration_method`, `metrics_json`); Produktion laedt nur Laeufe, die der Registry-Policy entsprechen.
- **Inferenz:** Shrink-Metriken sind in `hybrid_decision.hybrid_decision.prob_shrink_reasons` und `take_trade_prob_adjusted_0_1` sichtbar; Lane-Gruende in `meta_lane_reasons`.

## Konfiguration (Auszug)

| Umgebungsvariable                     | Bedeutung                                                                                    |
| ------------------------------------- | -------------------------------------------------------------------------------------------- |
| `META_PROB_OOD_SHRINK_FACTOR`         | Staerke der Prob-Zentrierung bei OOD                                                         |
| `META_PROB_UNCERTAINTY_SHRINK_WEIGHT` | Einfluss der Modell-Unsicherheit auf Shrink                                                  |
| `META_LANE_PAPER_*`                   | Schwellen fuer `paper_only` (Prob-Band, Uncertainty, Execution-Cost, Risk/History/Structure) |

Schema-Version Modell-Output: `MODEL_OUTPUT_SCHEMA_VERSION` 7.1 inkl. optionalem Feld `meta_trade_lane` im Contract-Snapshot.
