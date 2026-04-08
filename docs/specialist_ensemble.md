# Spezialisten-Ensemble (hierarchisch, deterministisch)

## Ueberblick

Die Signal-Engine stapelt **sieben deterministische Spezialisten-Ebenen** vor dem Router:

1. **base** — Scoring-/Hybrid-/Take-Trade-Kontext (`signal_row`)
2. **family** — Marktfamilie, Long/Short-Blocker, Family-Penalties
3. **product_margin** — Produkttyp, Margin-Modus, Hebel-Band-Hints
4. **liquidity_vol_cluster** — Spread-/RV-Cluster-/Kosten-Label (`liqvol:…`), kein Symbol-„Experte“
5. **regime** — Regime-State, Bias, Exit-Hints
6. **playbook** — Registry-Auswahl, Score, Exit-Familien
7. **symbol** — nur bei **nachgewiesener Datensuffizienz** (`symbol:SYMBOL`); sonst **Cluster-Fallback**
   `cluster:family_xs:{family}` mit hoher Abstinenz — kein falscher Symbol-Experte.

Ein **Gegnercheck (Adversary)** prueft OOD, Regime/Playbook-Konsistenz, Regime-Bias vs. Signalrichtung,
Drei-Wege-Spaltung (Long/Short/Neutral), Edge-Dispersion und klassischen Richtungsdissens.

Der **Router** (`deterministic_specialist_router_v2`) entscheidet ausschliesslich aus Pipeline-
`trade_action`, Playbook-/Family-Gates und dem Adversary-Output — **ohne LLM**.

Audit: `ensemble_hierarchy`, `specialist_proposals_all`, pro Layer `proposal` im Snapshot.

## Versionen (Audit)

| Artefakt        | Konstante                                              | Ort                                      |
| --------------- | ------------------------------------------------------ | ---------------------------------------- |
| Proposal-Schema | `SPECIALIST_PROPOSAL_VERSION` (`1.1`)                  | `shared_py.specialist_ensemble_contract` |
| Router          | `ENSEMBLE_ROUTER_VERSION` (`ensemble-router-v3`)       | `shared_py.specialist_ensemble_contract` |
| Adversary       | `ENSEMBLE_ADVERSARY_VERSION` (`ensemble-adversary-v2`) | `specialist_proposals.py`                |
| Router-Instanz  | `router_id`                                            | `specialists.router_arbitration`         |

## Strukturiertes Proposal (`SpecialistProposalV1`)

Siehe TypedDict in `specialist_ensemble_contract.py`:

- **direction**, **no_trade_probability_0_1**, **expected_edge_bps**
- **expected_mae_bps** / **expected_mfe_bps** (aus `signal_row`, wenn gesetzt)
- **exit_family_primary**, **exit_families_ranked**
- **stop_budget_0_1** und Spiegel **stop_budget_hint_0_1** (Audit/Operator-UI)
- **leverage_band** und Spiegel **leverage_band_hint**
- **uncertainty_0_1**, **reasons**

## Training- und Inferenz-Scope

| Spezialist                | Inferenz-Inputs                                                        |
| ------------------------- | ---------------------------------------------------------------------- |
| **base**                  | `signal_row`, Composite, Projektionen                                  |
| **family**                | `BitgetInstrumentIdentity`, Blocker                                    |
| **product_margin**        | Family, `product_type`, `margin_account_mode`                          |
| **liquidity_vol_cluster** | Primary-Features: Spread, RV-Cluster, Execution-Cost, Completeness     |
| **regime**                | `regime_state`, Bias, Confidence                                       |
| **playbook**              | Registry-Scores, Primary-Features                                      |
| **symbol**                | Gleiche Features + Suffizienz-Gate; sonst Family-Cross-Section-Cluster |

## Adversary-Regeln (Kurz)

| Flag                      | Bedingung                                                                                               | Router bei vorher `allow_trade`             |
| ------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| hard_veto                 | OOD-Alert oder harter OOD-Score                                                                         | `do_not_trade`                              |
| regime_mismatch_veto      | Playbook-`regime_suitability` verletzt oder Trend-Playbook in Compression/Chop mit niedriger Confluence | `do_not_trade`                              |
| tri_way_veto              | signifikante Masse gleichzeitig Long, Short und Neutral                                                 | `do_not_trade`                              |
| edge_dispersion_veto      | Spanne der `expected_edge_bps` über ≥3 Spezialisten zu gross                                            | `do_not_trade`                              |
| regime_bias_conflict_veto | `regime_bias` entgegen `direction` bei ausreichender Regime-Confidence                                  | `do_not_trade`                              |
| directional_veto          | gewichteter Long/Short-Dissens (Ratio-Schwelle)                                                         | `do_not_trade`                              |
| confidence_shrink         | moderater Dissens ohne harten Veto                                                                      | Multiplikator auf `decision_confidence_0_1` |

Zusaetzlich: **Regime-Stimme** erhaelt bei Bias-vs.-Signal-Konflikt einen dokumentierten Massen-Boost
(`adversary_regime_signal_direction_conflict_boost`).

## Operator-Sicht / Dashboard

- `source_snapshot_json.specialists`: alle Layer inkl. `symbol_specialist.symbol_expert_mode`
  (`symbol_active` \| `cluster_family_cross_section`).
- `reasons_json.specialists` / `signal_components_history_json.layer=specialist_router`:
  vollstaendiger Stack + Adversary.
- Live-Forensik: `shared_py.observability.execution_forensic` aggregiert Proposal-Summaries
  (Richtung, Edge, MAE/MFE, Stop-/Uncertainty-Hints) je Spezialist.

## Tests

- `tests/signal_engine/test_specialist_router.py`
- `tests/signal_engine/test_specialist_ensemble_adversary.py`
- `tests/signal_engine/test_specialist_hierarchy_adversary.py`

Siehe auch `docs/signal_engine_end_decision.md` (`decision_control_flow`).
