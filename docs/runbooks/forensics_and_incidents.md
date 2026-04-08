# Forensik, SLOs und Incident-Massnahmen

## Ziele

- **Ursachen** bei Erfolg/Fehler/Desync/Verlustphasen nachvollziehbar machen, ohne Secrets oder LLM-Rohprompts in Logs/API-Antworten.
- **SLOs** ueber Monitor-Engine (Prometheus-Gauges + `ops.alerts`) mit klaren Operator-Schritten.

## Datenpfade (kanonisch)

| Artefakt                                | Ort                                                                        | Hinweis                                                                                                            |
| --------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Spezialisten/Router-Snapshot (operativ) | `app.signals_v1.reasons_json`, `source_snapshot_json`                      | Signal-Engine persistiert Stack                                                                                    |
| Execution-Entscheid + Trace             | `live.execution_decisions`                                                 | `payload_json` / `trace_json` (Gateway-Timeline redacted)                                                          |
| **Forensic-Snapshot** (journal)         | `live.execution_journal.details_json.forensic_snapshot`                    | Ab aktuellem Stand mit Spezialisten-, No-Trade-, Stop-Budget- und Instrument-Metadaten-Summary; `schema_version=2` |
| Operator-Freigabe                       | `live.execution_operator_releases` + Journal-Phase `operator_release`      | Telegram aendert keine Strategie-Policy                                                                            |
| Orders/Fills/Actions                    | `live.orders`, `live.fills`, `live.order_actions`                          | `source_execution_decision_id` verknuepft                                                                          |
| Shadow-Gate                             | `live.shadow_live_assessments`                                             | `match_ok`, `report_json`                                                                                          |
| Risk-Sidecar                            | `live.execution_risk_snapshots`                                            | Deterministische Risk-Engine-Zusammenfassung                                                                       |
| Telegram-Operator-Audit                 | `alert.operator_action_audit`, `alert.alert_outbox`                        | Pending/Execute/HTTP-/Delivery-Spur, ohne Strategiemutation                                                        |
| Learning / Review                       | `learn.e2e_decision_records`, `learn.trade_evaluations`, `paper.positions` | Outcome, Review, QC, Paper-vs-Live-Kontext                                                                         |
| Gateway-Auth-/Mutation-Audit            | `app.gateway_request_audit`                                                | inkl. `auth_failure_*`, Manual-Action und Operator-Release                                                         |

## API: Trade-Timeline (aggregiert)

- **Gateway (auth-pflichtig):** `GET /v1/live-broker/executions/{execution_id}/forensic-timeline`
- Audit-Aktion: `live_broker_forensic_timeline_view` (`app.gateway_request_audit`)
- Antwort (Schema **3** / `forensic_model_version: forensic-timeline-v3`):
  - **Kanonische Zeitachse:** `timeline_sorted` (alle Events sortiert).
  - **Phasen-Index:** `forensic_phases` — verweist pro Phase auf Indizes in `timeline_sorted` (kein Daten-Duplikat).
  - **Signalpfad kompakt:** `signal_path_summary` — Spezialisten, Router, Stop-Budget, DCF, Risk/Shadow (Journal-kompatibles `build_live_broker_forensic_snapshot`).
  - **Korrelation:** `correlation.execution_id`, `correlation.signal_id`, optional `correlation.correlation_chain` aus `source_snapshot_json`.
  - Weiterhin: Decision (redacted), Signal-Kontext, Journal, Release, Orders, Fills, Exit-Plaene, Order-Actions, Audits, Shadow/Risk, Telegram, Outbox, Learning/E2E, Paper/Review, Gateway-Audit.
- **Marker:** `specialist_path_marker`-Event verweist explizit auf `signal_path_summary` fuer Spezialisten-/Decision-Flow-Details.

## Dashboard

- Route: `/console/live-broker/forensic/{executionId}` (Server-Component, Gateway-Backend).
- Zweck: Trade-Kausalkette lesen, nicht mutieren. Die Seite zeigt Kontext, Timeline, Risk-/Shadow-Bloecke, Telegram-/Gateway-Audit und Learning-/Review-Spuren.

## Prometheus (Monitor-Engine)

Neu/ergaenzend u. a.:

- `signal_do_not_trade_ratio_1h`
- `signal_stop_fragility_p90_24h`
- `alert_outbox_failed_24h`

Bestehend: `live_reconcile_drift_total`, `shadow_live_match_failures_24h`, `data_freshness_seconds`, Stream-Lag, …

## SQL-SLO-Alerts (`ops.alerts`)

Schwellen per ENV (siehe `.env.example`):

| alert_key (Beispiel)                         | Bedeutung                                 | Typische Massnahme                                                      |
| -------------------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| `trading:signal_do_not_trade_spike_1h`       | Hoher Anteil `do_not_trade`/`abstain`     | Regime/Daten/Drift pruefen; kein Hebel hochdrehen                       |
| `trading:signal_stop_fragility_p90_elevated` | Stops strukturell fragil                  | Spread/Ticksize/Hebel-Kurve; ggf. Universum eingrenzen                  |
| `trading:signal_router_instability_24h`      | Hauefige Router-Wechsel                   | Router-/Playbook-Drift, Regime-Flattern, Scope-Probleme pruefen         |
| `trading:specialist_disagreement_ratio_24h`  | Hoher Ensemble-/Adversary-Dissent         | Family-/Regime-/Playbook-Konflikte, Daten- und Kontextqualitaet pruefen |
| `trading:telegram_outbox_failures_24h`       | Telegram-Versand                          | Alert-Engine-Logs, Bot-Token/Netzwerk, Outbox-Retry                     |
| `trading:telegram_operator_errors_24h`       | Telegram-Freigabe-/Notfallpfad fehlerhaft | `alert.operator_action_audit`, Upstream-HTTP, Bestätigungspfad          |
| `trading:gateway_auth_failures_1h`           | Auth-/Manual-Action-Anomalie              | `app.gateway_request_audit`, Rollen/Token/Rate-Limits prüfen            |
| `trading:live_reconcile_drift_elevated`      | Reconcile-Drift                           | `docs/recovery_runbook.md`, Private-WS, Exchange-Truth                  |

Deaktivieren: `MONITOR_TRADING_SQL_ALERTS_ENABLED=false` (nur wenn bewusst).

## Incident-Typen (Kurz)

### 1. Stale Daten (`freshness:*`, `stream:*`)

1. Pruefen: `monitor-engine` Prometheus `data_freshness_seconds`, Stream-Lag.
2. Market-Stream / Feature-Pipeline; ggf. einzelnes Symbol-Feed.
3. Keine manuellen Strategie-Aenderungen ueber Chat.

### 2. Shadow/Live-Divergenz (`svc:live-broker:shadow_live_divergence`, `trading:live_reconcile_drift_elevated`)

1. Letzte `live.reconcile_snapshots.details_json.drift`.
2. Journal + Timeline fuer betroffene `execution_id` lesen: `signal_context`, `shadow_live_assessment`, `risk_snapshot`, `telegram_operator_actions`, `gateway_audit_trails`.
3. Live-Submit nur nach Gate-Policy; Safety-Latch beachten (`docs/emergency_runbook.md`).

### 3. No-Trade-Spike / hohe Stop-Fragilitaet

1. Stichprobe `app.signals_v1` + Signal-Detail im Dashboard.
2. Router-Log-Zeilen `signal_engine.service`: `specialist_stack ... dissent=... operator_gate=... stop_fragility=...`.
3. In der Execution-/Signal-Forensik `decision_control_flow.no_trade_path`, `forensic_snapshot.specialists`, `forensic_snapshot.stop_budget`.
4. Learning/Drift: `learn.online_drift_state`, `learn.drift_events`.

### 4. Telegram / Outbox

1. `alert.alert_outbox` `state=failed`, `last_error`, plus `alert.operator_action_audit`.
2. Alert-Engine-Health; Webhook/Long-Poll-Modus; Timeline zeigt `telegram_operator_actions` und `telegram_alert_outbox`.
3. Normale App-Logs sind auf redigierte Chat-/User-Referenzen reduziert; fuer tiefe Analyse nur Audit-Tabellen und `execution_id`/`pending_id` verwenden.

### 5. Auth-/Gateway-Anomalien

1. `app.gateway_request_audit action LIKE 'auth_failure_%'` nach Pfad/Aktion lesen.
2. Typische Pfade: sensitive read, admin write, live-broker mutation, fehlendes Manual-Action-Token.
3. Rate-Limits, JWT-/Internal-Key-Verteilung und offene interne Routen pruefen. Keine Authorization-Header in Klartext loggen.

## Logging-Regeln (Produktion)

- **Keine** vollstaendigen Prompts, Chat-Verlaeufe oder API-Secrets in App-Logs.
- Gateway-Audit: `detail_json` rekursiv redacted; keine `token`, `messages`, `prompt`, `chat_id`, `user_id`, … (siehe `api_gateway/audit.py` und `shared_py.observability.execution_forensic`).
- LLM-Services: nur Metriken/Fehlerklassen, keine Nutzer-Rohtexte exportieren.

## Offene Erweiterungen (kein Blocker)

- Signal-zentrierte Forensik-Ansicht fuer reine `no_trade`-Faelle ohne nachgelagerte `execution_id`.
- Tieferes Correlation-Modell fuer Paper-`strategy_events` bis in dieselbe Timeline.
