# Vereinheitlichte Exit-Engine (`shared-exit-v2`)

Implementierung: `shared/python/src/shared_py/exit_engine.py`  
Nutzer: **Paper-Broker** (`evaluate_exit_plan` mit `now_ms`), **Live-Broker** (Planbau + Validierung + Ausfuehrungslog).

## Fachpfad (eine Bewertungskette)

Die Reihenfolge ist in `EXIT_EVALUATION_ORDER_DE` festgelegt und wird in `evaluate_exit_plan` / `run_unified_exit_evaluation` abgearbeitet:

1. **Emergency-Flatten** — `stop_plan.force_emergency_close` (Disconnect / Kill / manuelle Flatten), danach Flag wird geloescht.
2. **Time-Stop** — `time_stop.deadline_ts_ms` <= `now_ms` → Vollschliessung, `fired: true`.
3. **Stop-Loss** — mark/fill gemaess `trigger_type`.
4. **Trailing / Runner** — nach Armierung, Treffer auf `trail_stop`.
5. **Teilgewinne (Partial)** — TP-Stufen, `reduce_only` aus `execution`.
6. **Break-Even** — Stop-Anhebung nach konfiguriertem TP-Index.
7. **Trailing-State-Update** — High/Low-Water ohne sofortigen Close.

Alle Schliessungen laufen ueber dieselbe **Execution-Semantik** (`execution.reduce_only`, `order_type`, `timing`).

## Parameter aus MAE, MFE, Regime, Liquiditaet

- `adjust_stop_take_for_mae_mfe`: verschiebt Stop/TP konservativ anhand erwarteter **MAE/MFE** (bps), **Regime** (choppy/range/volatile/shock), **Spread** und **Tiefe** (`depth_ratio`).
- Live-Broker: Aufruf beim Planbau, wenn `signal_trace` Felder `expected_mae_bps` / `expected_mfe_bps` / `market_regime` enthaelt.
- Optional: `exit_time_stop_deadline_ts_ms` im Trace → `build_live_exit_plans(..., time_stop_deadline_ts_ms=...)`.

## Exit-Familien (adaptiv, deterministisch)

- **Resolver:** `shared_py.exit_family_resolver.resolve_exit_family_resolution` kombiniert Ensemble-Ranking aus `end_decision_binding` mit Playbook-/Regime-/MFE-MAE-, Spread-, Funding/Basis- und News-Signalen. Ergebnis: `decision_control_flow.exit_family_resolution` plus Felder auf `end_decision_binding` (`exit_family_effective_primary`, `exit_families_effective_ranked`, `exit_resolution_drivers`, `exit_execution_hints`, `exit_family_resolution_version`).
- **Gleiche Exit-Semantik Paper/Live:** `merge_exit_build_overrides` + optional `runner_arm_after_tp_index` in `build_live_exit_plans` passen Teilgewicht, Runner und Break-Even an die `execution_hints` an. Live-Broker und Paper-`build_tp_plan` nutzen dieselbe Helper-Kette; Unterschiede entstehen nur aus Preis-/Planbau (ATR vs. finales TP-Ziel), nicht aus widersprüchlicher Policy-Logik.
- **Learning:** `build_model_output_snapshot` spiegelt `exit_family_resolution` aus `reasons_json.decision_control_flow` in kompakte Signal-Snapshots für spätere Auswertung.

## Liquidations- und Boersenrealismus

- `validate_exit_plan`: optional **Liquidations-Puffer** (`check_liquidation_buffer`, `approximate_isolated_liquidation_price` — grobe Linear-Naeherung, kein Exchange-Ersatz).
- **Gap / Spread-Risiko**: wenn `mark_price` und `fill_price` gesetzt sind und das Spread-Verhaeltnis zur Stop-Distanz zu gross ist → `exit_plan_exit_plan_gap_stop_too_tight_vs_spread`.
- Bestehende Regeln: Hebel vs. `allowed_leverage`, Positionsrisiko, TP-Prozentsumme, Preisrelationen Long/Short.

## Absicht vs. Ausfuehrung (Qualitaetsanalyse)

- **`context_json.exit_intent_json`**: feste Snapshot-Struktur (`build_exit_intent_document`) — geplante Stops/TPs, MAE/MFE-Inputs, Adjustments.
- **`context_json.execution_log_json`** (Live): jede ausgefuehrte Exit-Order-Zeile aus dem Monitor-Tick (`ts_ms`, `executed_action`, Mark/Fill, Policy-Version).

Paper: weiterhin `position_events` (TP_HIT, SL_HIT, TRAILING_UPDATE, …) als Ausfuehrungsspur.

## Disconnect, Restart, Emergency

| Szenario              | Verhalten                                                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Disconnect**        | Keine Preis-Ticks: Engine wertet nicht aus. Beim Wiederonline laufen dieselben Plaene weiter; fehlende Kerzen koennen zu verzoegerten Stops fuehren — Exchange-Trigger (mark) bleiben massgeblich.                  |
| **Restart**           | Live: `stop_plan_json` / `tp_plan_json` und `context_json` persistiert → `run_once` setzt mit gespeichertem Runner-/TP-State fort. `force_emergency_close` nur setzen, wenn beim Start bewusst flatten werden soll. |
| **Emergency-Flatten** | `force_emergency_close` auf dem **Stop-Plan** setzen; naechster `evaluate_exit_plan`-Durchlauf schliesst voll mit `emergency_flatten`.                                                                              |

Siehe auch `docs/stop_tp.md` (Trigger-Typen, Paper/Live-Paritaet).
