# SLOs / SLIs — Betriebsvertrag (Observability)

**Kurz-Playbook, Kettenuebersicht und KI-SLOs:** [`OBSERVABILITY_AND_SLOS.md`](../OBSERVABILITY_AND_SLOS.md).

Dieses Dokument definiert **Service Level Indicators** und Zielrichtungen (**SLO-Ziele**), die ueber Prometheus-Metriken und Alerts durchgesetzt werden. Abweichungen sind **Incident-Kandidaten**, keine kosmetischen Hinweise.

## Daten & Queues

| SLI                                      | Metrik / Quelle                                  | Zielrichtung                     | Harte Alerts (Auszug)                          |
| ---------------------------------------- | ------------------------------------------------ | -------------------------------- | ---------------------------------------------- |
| Kerzen-Staleness                         | `data_freshness_seconds{datapoint="candles_1m"}` | < 180 s unter Normalbetrieb      | `DataStaleCandles1m`                           |
| Signal-Staleness                         | `data_freshness_seconds{datapoint="signals"}`    | < 300 s                          | `DataStaleSignals`                             |
| Redis Stream Lag                         | `redis_stream_lag`                               | < 5000 (Warn), < 25000 (hart)    | `RedisStreamLagHigh`, `RedisStreamLagCritical` |
| Signal-Pipeline Latenz (Feature→Analyse) | `signal_pipeline_lag_p95_seconds_1h`             | P95 < 180 s wenn Daten vorhanden | `SignalPipelineLagP95High`                     |

## Signalqualitaet & Modell

| SLI                         | Metrik                                     | Zielrichtung                           | Alerts                                                       |
| --------------------------- | ------------------------------------------ | -------------------------------------- | ------------------------------------------------------------ |
| No-Trade-Anteil             | `signal_do_not_trade_ratio_1h`             | Kontextabhaengig; Spike > 0.82 pruefen | `SignalDoNotTradeSpike`                                      |
| Stop-Fragilitaet P90        | `signal_stop_fragility_p90_24h`            | < 0.78 typisch                         | `SignalStopFragilityElevated`                                |
| Spezialisten-Dissent-Anteil | `signal_specialist_disagreement_ratio_24h` | < 0.35 Warn, < 0.55 kritisch           | `SpecialistDisagreementHigh`, `SpecialistDisagreementSevere` |
| Online-Drift                | `online_drift_action_rank`                 | 0–1 normal; 2 shadow_only; 3 block     | `OnlineDriftShadowOnly`, `OnlineDriftHardBlock`              |
| Drift-Events                | `learn_drift_events_24h`                   | stabil; Spike > 10                     | `LearnDriftEventsSpike`                                      |
| Drift-/Shadow-Executions    | `execution_drift_or_shadow_decisions_24h`  | wenige; > 8 / 24h pruefen              | `DriftLinkedExecutionDecisionsElevated`                      |

## Live-Geld & Ausfuehrung

| SLI              | Metrik                                                          | Zielrichtung    | Alerts                   |
| ---------------- | --------------------------------------------------------------- | --------------- | ------------------------ |
| Shadow/Live Gate | `shadow_live_gate_blocks_24h`, `shadow_live_match_failures_24h` | 0 Bloecke ideal | `ShadowLiveGateActivity` |
| Reconcile-Alter  | `live_reconcile_age_ms`                                         | < 90 s          | `ReconcileLagHigh`       |
| Kill-Switch      | `live_kill_switch_active_count`                                 | 0               | `KillSwitchActive`       |
| Safety-Latch     | `live_safety_latch_active`                                      | 0               | `SafetyLatchActive`      |
| Order-Failrate   | `live_order_fail_rate_1h`                                       | < 15 %          | `LiveOrderFailRateHigh`  |
| Exit-Fehler      | `live_order_exit_failures_1h`                                   | 0               | `LiveOrderExitFailures`  |

## Sicherheit & Governance

| SLI                             | Metrik                                   | Zielrichtung | Alerts                         |
| ------------------------------- | ---------------------------------------- | ------------ | ------------------------------ |
| Gateway-Auth-Failures (gesamt)  | `gateway_auth_failures_1h`               | niedrig      | `GatewayAuthAnomalies`         |
| Manuelle Aktion / Live-Mutation | `gateway_manual_action_auth_failures_1h` | 0–2          | `ManualLiveBrokerAuthFailures` |
| Billing-Lese-Auth               | `commerce_billing_auth_failures_1h`      | 0–3          | `CommerceBillingAuthFailures`  |

## Kommerziell

| SLI                | Metrik                     | Zielrichtung         | Alerts                     |
| ------------------ | -------------------------- | -------------------- | -------------------------- |
| Ledger-Schreibrate | `commerce_ledger_lines_1h` | erwartbar pro Tenant | `CommerceLedgerWriteSpike` |

## Monitor-Engine (Meta-SLO)

| SLI            | Metrik                                           | Zielrichtung         | Alerts                     |
| -------------- | ------------------------------------------------ | -------------------- | -------------------------- |
| Tick laeuft    | `monitor_engine_tick_duration_seconds_count`     | staendige Increments | `MonitorEngineTickStalled` |
| Tick-Dauer P90 | Histogram `monitor_engine_tick_duration_seconds` | P90 < 45 s           | `MonitorEngineTickSlowP90` |

## Audit-Korrelation

- Gateway: strukturiertes Logfeld `corr_gateway_audit_id` je persistierter Zeile (`app.gateway_request_audit.id`).
- Live: bestehende Felder `corr_signal_id`, `corr_execution_id`, … siehe `shared_py.observability.correlation`.
- Forensik-API: `GET /v1/live-broker/executions/{id}/forensic-timeline` liefert `correlation`, `forensic_phases`, `signal_path_summary`, `schema_version`.

Schwellen sind in `infra/observability/prometheus-alerts.yml` zentral; Aenderungen nur mit Runbook-Update.
