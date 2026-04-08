# E2E Decision Learning Records (`learn.e2e_decision_records`)

## Zweck

Pro **Signal** (`signal_id` UNIQUE) wird ein auditierter Lern-Datensatz persistiert, der:

- Spezialisten-/Router-Votes und finale Gates abbildet,
- Stop-Budget, Fragilität, Exit-Hinweise und Kontext (inkl. SMC) festhaelt,
- **Outcomes** nach Ausführungs-Lane trennt: `paper`, optional `shadow`, `live_mirror`, `counterfactual`,
- **QC-Labels** für Training/Governance vorbereitet (heuristisch + erweiterbar um Human-Labels).

Die Handelsentscheidung bleibt im Signal-Engine-/Broker-Pfad; diese Tabelle ist **nur** Beobachtung und Lernsubstrat.

## Lebenszyklus

| Event                  | Aktion                                                                                                |
| ---------------------- | ----------------------------------------------------------------------------------------------------- |
| `signal_created`       | `upsert` Zeile: `snapshot_json`, initiale `outcomes_json` (u. a. `counterfactual` bei `do_not_trade`) |
| `trade_opened` (Paper) | `paper_trade_id`, `outcomes_json.paper.phase=open`                                                    |
| `trade_closed` (Paper) | `trade_evaluation_id`, geschlossenes `outcomes_json.paper`, Merge in `label_qc_json`                  |

Fehlt der Eintrag bei `trade_closed` (z. B. verpasstes `signal_created`), wird er aus `app.signals_v1` nachgetragen (`ensure_record_from_signal_if_missing`).

## Spalten (Kurz)

| Spalte                         | Inhalt                                                                                                                 |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `snapshot_json`                | Version `e2e-snapshot-v1`: siehe `learning_engine.e2e.snapshot.build_e2e_snapshot_from_signal_row`                     |
| `outcomes_json`                | Keys: `paper`, `shadow`, `live_mirror`, `counterfactual` — `null` bis bekannt                                          |
| `label_qc_json`                | u. a. `stop_too_tight`, `late_entry_stale_signal`, `false_positive_trade_hypothesis`, `poor_exit_selection_hypothesis` |
| `operator_mirror_actions_json` | Array von Hinweisen (z. B. Meta-Keys), **keine** Telegram-Strategie-Mutation                                           |

## QC / Human Labels

- Automatisch beim Paper-Close aus `rules_v1`-Labels und einfachen Heuristiken (`learning_engine.e2e.qc`).
- **`missed_move`**, **`manual_override`**: Slots für spätere Operator-Tools / API — Struktur `label_qc_json` ist merge-freundlich (JSONB `||`).

## API

`GET /learning/e2e/recent?limit=50` — Operator-/Dashboard-Sicht (read-only).

## Migration

`infra/migrations/postgres/540_e2e_decision_learning.sql`

## Trainingsnutzung

Downstream-Builder können `learn.e2e_decision_records` mit `learn.trade_evaluations` über `signal_id` / `trade_evaluation_id` joinen. Shadow-/Live-Outcomes sind vorbereitet (`null`), sobald dedizierte Trade-IDs und Events angebunden sind.
