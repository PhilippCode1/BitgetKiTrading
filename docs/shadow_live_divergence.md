# Shadow vs. Live: Forensik und Blocker (Prompt 30)

## Messung

Modul `shared_py.shadow_live_forensics.compute_shadow_live_divergence(live_row, shadow_row)` erzeugt ein Dict mit:

| Feld                        | Bedeutung                                                            |
| --------------------------- | -------------------------------------------------------------------- |
| `data_age_delta_ms`         | Differenz max. Liquidity-/Feature-Alter (primary_tf + timeframes)    |
| `regime_match` / `regime_*` | Gleicher `market_regime`?                                            |
| `trade_action_match`        | `trade_action` Live vs Shadow                                        |
| `meta_lane_match`           | `meta_trade_lane` (Ausfuehrungsstufe)                                |
| `risk_governor_hard_*`      | Listen `hard_block_reasons_json` aus `hybrid_decision.risk_governor` |
| `take_trade_prob_delta`     | \|p_live − p_shadow\|                                                |
| `exit_stop_trigger_match`   | `stop_trigger_type` falls gesetzt                                    |
| `blockers`                  | Kurzcodes fuer fachliche Alerts                                      |
| `warnings`                  | Erwartbare oder quantitative Abweichungen                            |
| `correlation_*`             | Eingebettete `correlation_chain` aus Snapshots                       |

Speicherung: typischerweise als JSON (z. B. in Analytics-Runs, Reports oder als Teil eines Vergleichs-Tools) — **keine** zwingende neue DB-Spalte; optional in `source_snapshot_json` bei Shadow-Tools.

## Erwartbar (kein automatischer Blocker)

- **Kleine `data_age_delta_ms` &lt; wenige Sekunden**: unterschiedliche Verarbeitungszeit / parallele Pfade.
- **Moderate `take_trade_prob_delta`**: unterschiedliche Modell-Runs (Champion vs Challenger) — bis Schwellen in `warnings`.
- **Regime-Mismatch bei niedriger Konfidenz**: kann Rauschen sein; mit `regime_confidence_0_1` im Snapshot manuell pruefen.

## Blocker (in `blockers` — fachlich eskalieren)

- `shadow_blocks_trade_live_would_allow` / `live_blocks_trade_shadow_would_allow`: entgegengesetzte Handelsfreigabe.
- `meta_trade_lane_mismatch`: eine Seite z. B. `candidate_for_live`, andere `shadow_only` / `do_not_trade`.
- `risk_governor_hard_reasons_differ`: unterschiedliche harte Risk-Gates (Margin, Drawdown, Health, …).
- `market_regime_mismatch`: konsistente Regime-Klassifikation verletzt (bei gleichem Kontext verdächtig).

## Replay-Paritaet

Replay-Ketten tragen `correlation_chain` und bei Replay `deterministische signal_id` (siehe `docs/replay_determinism.md`). Vergleiche Shadow-vs-Live **auf derselben `replay_session_id` und demselben `upstream_drawing_updated_event_id`**, sonst sind Abweichungen trivial.

## Broker-Realitaet

Echte Boersen-/Paper-Fills, Slippage und Orderbuch sind **nicht** in der reinen Signal-Zeile; Abweichungen zwischen Live-Execution und Shadow-Record gehoeren in **Execution-/Broker-Logs** (`internal_order_id`, Fill-Events). Die Forensik hier deckt **Signal- und Decision-Layer** ab; Erweiterung um Fill-Deltas ist ein separates Thema.
