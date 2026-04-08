# Stop-Budget- und Ausfuehrbarkeits-Policy (Signal-Engine)

**Version:** `stop-budget-v2` (`STOP_BUDGET_POLICY_VERSION` in `signal_engine/stop_budget_policy.py`).

## Kurzbeschreibung

Nach der Hybrid-/Hebel-Schicht wird jeder **allow_trade**-Kandidat mit **zeichnerischem Stop** gegen eine **hebel-indexierte Maximal-Distanz** und eine **Mindest-Distanz aus Marktmechanik** geprueft. Ziel: enge Stop-Disziplin ohne strukturell unhaltbare Orders.

## Hebel-Kurve

- Bis einschliesslich `STOP_BUDGET_ANCHOR_LEVERAGE` (Default **7**): maximaler geplanter Stop-Abstand **`STOP_BUDGET_MAX_PCT_AT_ANCHOR`** (Default **1,0 %**).
- Ab dort linear bis `STOP_BUDGET_HIGH_LEVERAGE_FLOOR` (Default **50**): Budget faellt auf **`STOP_BUDGET_FLOOR_PCT`** (Default **0,10 %**).

`max_stop_budget_pct_for_leverage(L)` implementiert die Kurve deterministisch.

## Mindest-Abstand (Ausfuehrbarkeit)

Konservatives Maximum aus (jeweils als Anteil vom Preis, family-/regime-skalierbar):

- **Tick:** `price_tick_size` aus Instrumentenkatalog × `STOP_BUDGET_TICK_STEPS_MIN`
- **Spread** × `STOP_BUDGET_SPREAD_FLOOR_MULT`
- **ATRP** × `STOP_BUDGET_ATR_FLOOR_MULT`
- **Impact** (Richtung) × `STOP_BUDGET_IMPACT_FLOOR_MULT`
- **Execution + Volatility-Cost** × `STOP_BUDGET_SLIPPAGE_FLOOR_MULT`
- **MAE (bps)** als Struktur-/Invalidierungs-Proxy × `STOP_BUDGET_MAE_STRUCTURE_MULT`

Zusaetzlich: `STOP_BUDGET_MIN_EXECUTABLE_FLOOR_PCT` als absoluter Untergrenzen-Fallback.

## Harte Entscheidungen

| Situation                                                                           | Aktion                                              |
| ----------------------------------------------------------------------------------- | --------------------------------------------------- |
| Stop-Zone nicht protektiv (falsche Seite)                                           | **blocked**, `rejected`                             |
| Stop weiter als globales 1 %-Cap (Anchor-Max)                                       | **blocked**                                         |
| Stop enger als Mindest-Ausfuehrbarkeit (`STOP_BUDGET_HARD_FRAGILITY_ABSTAIN`)       | **blocked**                                         |
| Hoher Liquidations-Stress + extrem enger Stop                                       | **blocked** (Schwellen `STOP_BUDGET_LIQUIDATION_*`) |
| Stop weiter als Budget bei aktuellem Hebel, aber bei niedrigerem L innerhalb Budget | **leverage_reduced**                                |
| Kein Hebel im erlaubten Band erfuellt Budget                                        | **blocked**                                         |

## Aufloesung bei untragbarem Stop (kanonisch)

1. **Hebel reduzieren**, solange ein Hebel im erlaubten Band das Stop-Budget erfuellt (`leverage_reduced`).
2. Sonst **Exit-/Playbook-Alternativen** aus Spezialisten-Grund (`exit_family_alternatives_json`, `resolution_ladder_json`) — nur Hinweis/Audit, kein erzwungener Trade.
3. Sonst **`do_not_trade`** / blocked mit `unsatisfiable` in den Reasons.

## Audit- und Lernfelder

Persistiert in `app.signals_v1` (Migration `520_stop_budget_audit.sql`) und in `source_snapshot_json.stop_budget_assessment` / `reasons_json.stop_budget_assessment`:

- `stop_distance_pct`, `stop_budget_max_pct_allowed`, `stop_min_executable_pct`
- `stop_to_spread_ratio`
- `stop_quality_0_1`, `stop_executability_0_1`, `stop_fragility_0_1`
- `stop_budget_policy_version`
- **v2:** `canonical_stop_budget_curve`, `resolution_ladder_json`, `exit_family_alternatives_json`, `stop_resolution_order_de`

**Mark- vs. Last:** `mark_trigger_note` dokumentiert `SIGNAL_DEFAULT_STOP_TRIGGER_TYPE` und optional `mark_index_spread_bps` aus Features.

## Laufzeit-Reihenfolge

Hybrid-Decision → **Stop-Budget** → Online-Drift → Spezialisten-Stack → **Unified Exit Plan** (`unified_exit_plan` im Snapshot) → `decision_control_flow` (Phase `stop_budget_executability`, Pipeline `se-end-decision-v3`).
