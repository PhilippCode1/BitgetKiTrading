# Operator-Statussprache

Dieses Dokument definiert die **kanonischen Statusbegriffe** fuer Doku,
Dashboard, Gateway, Telegram und Operator-Prozesse. Ziel ist, dass dieselben
Begriffe ueber alle Oberflaechen hinweg dieselbe Bedeutung tragen.

## Kernstatus

| Begriff                    | Bedeutung                                                                 | Quelle                                                                                         |
| -------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `allow_trade`              | Die deterministische Signal-/Risk-Kette erlaubt den Trade fachlich        | `app.signals_v1.trade_action`                                                                  |
| `do_not_trade`             | Die fachliche Kette bleibt bei No-Trade / Abstention                      | `app.signals_v1.trade_action`, `decision_control_flow.no_trade_path`                           |
| `shadow-only`              | Das System bleibt im Shadow-Pfad; keine echten Orders                     | `EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false`                                             |
| `candidate_for_live`       | Die Lane erlaubt eine Mirror-/Live-Pruefung                               | `meta_trade_lane`                                                                              |
| `live_mirror_eligible`     | Ein Kandidat darf in die enge Echtgeld-Mirror-Kohorte                     | `live.execution_decisions.payload_json.live_mirror_eligible`                                   |
| `operator_release_pending` | Ein `live_candidate_recorded` liegt vor, aber noch kein Operator-Release  | `decision_action=live_candidate_recorded` + kein Eintrag in `live.execution_operator_releases` |
| `operator_released`        | Die enge Echtgeld-Freigabe wurde explizit erteilt                         | `live.execution_operator_releases`                                                             |
| `shadow_live_match_ok`     | Shadow- und Live-Pfad sind fuer diesen Kandidaten konsistent genug        | `live.shadow_live_assessments`, `payload_json.shadow_live_divergence`                          |
| `reconcile_clean`          | Reconcile ohne relevante Drift / ohne aktiven Latch                       | `live.reconcile_snapshots`, `live.audit_trails`                                                |
| `kill_switch_active`       | Ein Kill-Switch blockiert normale Orderwege                               | `live.kill_switch_events`                                                                      |
| `safety_latch_active`      | Live-Firewall nach Reconcile-/Recovery-Problem ist aktiv                  | `live.audit_trails category=safety_latch`                                                      |
| `incident_free_runtime`    | Keine offenen kritischen Incidents / Audits im relevanten Freigabefenster | `ops.alerts`, `live.audit_trails`, Runbooks                                                    |

## Abgeleitete Operator-Begriffe

Diese Begriffe duerfen in Oberflaechen und SOPs verwendet werden, muessen aber
auf den obigen Primärdaten beruhen:

- **Mirror-Freigabe**: operatorischer Schritt, der aus `operator_release_pending`
  ein `operator_released` macht
- **Startkohorte**: enge Menge aus Familie, Symbolen, Playbook-Familien und Hebelstufe,
  die fuer Echtgeld-Mirror zugelassen ist
- **Ramp-Fallback**: Rueckfall auf `shadow-only` bei No-Go-Bedingungen
- **Post-Trade-Review**: nachgelagerte Bewertung in `learn.trade_evaluations` /
  `learn.e2e_decision_records`

## Telegram-Sprache

Telegram bleibt strikt lesend/bestaetigend:

- **lesen / erklaeren / bestaetigen / oeffnen / schliessen / abbrechen / Notfall**
- keine Strategie-, Modell-, Routing- oder Risk-Mutation

Empfohlene Begriffswahl in Telegram:

- `Mirror-Freigabe` statt allgemeines „KI-Plan freigeben“
- `operator_release_pending` / `operator_released` fuer bestehende `execution_id`
- `Notfall-Stopp` fuer Kill-Switch / Emergency-Flatten

## Dashboard-Sprache

Die UI darf kurze Lesebegriffe verwenden, muss aber auf die kanonischen Stati
abbildbar bleiben:

- `Mirror-Freigabe (Approval Queue)` -> `operator_release_pending`
- `Live Mirrors & Divergenz` -> `live_mirror_eligible`, `shadow_live_match_ok`
- `Signal & Risiko` -> `allow_trade` / `do_not_trade`, Stop-Budget, Governor
- `Trade-Forensik` -> End-to-End-Ansicht einer `execution_id`

## Gateway-Sprache

Der Gateway bleibt die kanonische Kontrollgrenze fuer:

- `manual action token`
- `operator_release`
- `kill-switch`
- `emergency_flatten`
- `sensitive read`

Die Begriffe aus diesem Dokument sollen in Operator-Doku und Antworten gleich
verwendet werden.
