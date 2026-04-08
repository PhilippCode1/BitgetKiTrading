# Signal-Engine: kontrollierter Endentscheid (Audit-Graph)

Version der Pipeline: **`se-end-decision-v4`** (`DECISION_PIPELINE_VERSION` in `decision_control_flow.py`).

## Entscheidungsreihenfolge (Laufzeit / Audit-Phasen)

1. **Datenqualitaet** — Quality-Gate / Feature-Gates (`source_snapshot_json.quality_gate`).
2. **Deterministische Safety** — Reject- und Downgrade-Regeln (`reasons_json.deterministic_gates`).
3. **Regime & Scoring** — `market_regime`, `regime_state`, Layer-Scores, heuristische Wahrscheinlichkeit (ohne LLM).
4. **Probabilistische Modelle** — Take-Trade, Return/MAE/MFE; Vollstaendigkeit als `ok` / `degraded`.
5. **Unsicherheit / OOD** — Kalibrierung, OOD, Ausfuehrungs-Lane (`uncertainty_gate_phase` u. a.); **no-trade** ist gleichwertiger Pfad.
6. **Hybrid, Risk-Governor, Hebel, Meta-Lane** — Ergebnis im Audit als `trade_action_after_hybrid_layer` aus `source_snapshot_json.hybrid_decision.trade_action`; finale Zeile kann danach vom Spezialisten-Router abweichen (`trade_action_final_on_row`).
7. **Stop-Budget / Ausfuehrbarkeit** — Hebel-indexierte Maximal-Distanz, Tick/Spread/ATR/Slippage-Mindestabstand, ggf. Hebelreduktion oder no_trade (`source_snapshot_json.stop_budget_assessment`). Details: `docs/stop_budget_policy.md`.
8. **Spezialisten-Arbitration** — Ensemble-Proposals, Playbook-Router, Adversary; **gebundene** Hinweise zu Playbook, Stop-Budget, Exit-Familien, Hebel-Band in `end_decision_binding`.
9. **Optional: Online-Drift** — Letzte harte Sperre bei aktivem Block.
10. **Meta-Decision-Kernel** — Fusion aus Hybrid, Risk-Governor, Spezialisten, Stop/Ausfuehrbarkeit, Datenqualitaet und Unsicherheit; finales **`meta_decision_action`** (siehe unten). Zielgroesse: erwarteter Nutzen unter Risiko (kalibrierter EU-Proxy in `meta_decision_bundle_json`), nicht maximale Aktivitaet.

## Strukturierte Artefakte

- **`reasons_json.decision_control_flow`** und Spiegel in **`source_snapshot_json.decision_control_flow`**:
  - `phases[]`: `id`, `order`, `title_de`, `outcome`, `evidence` (maschinenlesbar).
  - `end_decision_binding`: Playbook-Felder aus DB + konservative Aggregation aus Spezialisten-Proposals (Stop-Budget-Minimum, Exit-Ranking, Hebel-Band-Schnittmenge). Zusaetzlich **effektive Exit-Aufloesung**: `exit_family_effective_primary`, `exit_families_effective_ranked`, `exit_resolution_drivers`, `exit_execution_hints`, `exit_family_resolution_version` (Ensemble-Rohwerte bleiben in `exit_family_primary` / `exit_families_ranked`).
  - `exit_family_resolution`: vollstaendiges Resolver-Ergebnis inkl. Ensemble-Snapshot fuer Journal/Learning.
  - `no_trade_path`: Policy-Text, `phase_block_drivers`, Top-`abstention_reasons`.
  - `final_summary` inkl. Kurzreferenz auf Binding.
- **`reasons_json.specialists`** / **`source_snapshot_json.specialists`**: Rohdaten fuer Phase 8.
- Explain: `explain_long_json.sections.decision_pipeline` enthaelt `phases_structured`, `end_decision_binding`, `no_trade_path` (zusaetzlich zu `ordered_phases_de`).
- Events: `event_payload.decision_control_flow`, `decision_pipeline_version`.

## Meta-Decision-Kernel und Persistenz (API / Audit)

- **Spalten** `app.signals_v1`: `meta_decision_action`, `meta_decision_kernel_version`, `meta_decision_bundle_json`, `operator_override_audit_json` (Migration `550_meta_decision_kernel.sql`).
- **`meta_decision_action`** (finale Semantik, unabhaengig vom Legacy-Feld `trade_action`):
  - `do_not_trade` — Evidenz-basierte Abstinenz (Unsicherheit, Kalibrierung, OOD, Spezialisten-Divergenz, Datenqualitaet, Stop-Ausfuehrbarkeit, Portfolio-Universal-Blocks, negativer EU-Proxy, …).
  - `blocked_by_policy` — Policy-/Determinismus-Schicht (Drift-Hard-Block, deterministische Gates, Playbook-Blacklist, Regime-Policy, Family-Blocks, …).
  - `allow_trade_candidate` — positiver Kandidat ohne Live-Lane oder mit Paper/Shadow-Lane.
  - `candidate_for_live` — Lane `candidate_for_live` und keine Live-Execution-Sperre aus dem Risk-Governor.
  - `operator_release_pending` — Modell erlaubt Handel, aber **Live-Execution** oder **Operator-Gate** erfordert explizite Freigabe (`live_execution_block_reasons_json` / `operator_gate_required`).
- **`operator_override_audit_json`**: wird von der Signal-Engine **nicht** gesetzt. Ein Ueberschreiben von `blocked_by_policy` / `do_not_trade` fuer Live darf nur ueber **separate auditierte** Operator-Pfade erfolgen (z. B. `live.execution_operator_releases`, Eintraege im Execution-Journal) — kein stilles Ueberschreiben im Signal-Row ohne Audit-Spur.
- **JSON-Artefakte**: `reasons_json.meta_decision_kernel`, `source_snapshot_json.meta_decision_kernel`, `decision_control_flow.phases[]` (Phase `meta_decision_closure`), `decision_control_flow.final_summary` enthalten Kernel-Version, EU-Proxy und Abstinenz-Codes fuer UI, Burn-in, Shadow-vs-Live-Diff und Learning.
- **Dashboard/API**: Listen-Endpoint liefert `meta_decision_action` und `meta_decision_kernel_version` (siehe `db_dashboard_queries.fetch_signals_recent`); Detail nutzt `SELECT s.*`.

## No-Trade-Philosophie

Kein Nebenfehler: **no_trade** ist der konservative Standard bei Konflikten, OOD, harten Gates oder Router-Veto. **allow_trade** erfordert konsistente Freigaben ueber die dokumentierten Phasen.

## Randgrenzen

- News: Layer-Score und deterministische Shock-Regeln; kein LLM in der Kernpipeline.
- Telegram/Chat: keine Aenderung von Strategie-Parametern, Modellgewichten, Routing-Policies oder Risk-Limits; nur Lesen, Erklaeren und explizit freigegebene Order-Aktionen.
