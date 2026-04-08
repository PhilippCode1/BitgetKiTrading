# Monitoring & Systemgesundheit (Runbook)

Anker fuer Prometheus-`runbook`-Annotations (siehe `infra/observability/prometheus-alerts.yml`):

| Anker                                                                | Thema                                                 |
| -------------------------------------------------------------------- | ----------------------------------------------------- |
| `#kill-switch-active`                                                | Kill-Switch                                           |
| `#safety-latch`                                                      | Safety-Latch                                          |
| `#reconcile-lag` / `#reconcile-drift`                                | Reconcile                                             |
| `#shadow-live-gate` / `#replay-shadow-divergenz`                     | Shadow/Live                                           |
| `#online-drift`                                                      | Online-Drift                                          |
| `#kritische-audits` / `#risk-blocks`                                 | Audit / Risk                                          |
| `#router-instability` / `#specialist-disagreement`                   | Spezialisten / Router                                 |
| `#data-stale-candles` / `#data-stale-signals` / `#signal-throughput` | Datenfeed                                             |
| `#no-trade-spike` / `#stop-fragility`                                | Signal-/Stop-Qualitaet                                |
| `#llm-dlq`                                                           | LLM                                                   |
| `#redis-stream-lag`                                                  | Streams                                               |
| `#order-fail-rate` / `#exit-fehler`                                  | Orders                                                |
| `#learn-drift`                                                       | Learning                                              |
| `#telegram-delivery` / `#alert-backlog`                              | Alerting                                              |
| `#auth-anomalies`                                                    | Gateway / Auth                                        |
| `#monitor-tick-stalled` / `#monitor-tick-slow`                       | Monitor-Engine Scheduler                              |
| `#pipeline-lag-p95`                                                  | Signal-Pipeline Latenz                                |
| `#manual-action-misuse`                                              | Manuelle Tokens / Live-Mutationen                     |
| `#drift-execution-decisions`                                         | Drift-/Shadow-Execution                               |
| `#commerce-billing-auth` / `#commerce-ledger-spike`                  | Billing / Metering                                    |
| `#redis-stream-lag-critical`                                         | Queue harte Stufe                                     |
| `#online-drift-shadow-only`                                          | Drift shadow_only                                     |
| `#specialist-disagreement-severe`                                    | Spezialisten harte Stufe                              |
| `#bitget-llm-provider-health`                                        | Bitget/LLM: Keys, Demo vs. Live, Rate-Limits (Health) |

## bitget-llm-provider-health

1. **`GET /v1/system/health`** (Gateway, mit Operator-Aggregate-Auth wie fuer andere System-Health-Felder): Feld **`provider_ops_summary`** — **keine** Key-Werte, nur Booleans und Codes.
2. **`bitget`:** `exchange_mode` (`demo`/`live`), `credentials_complete`, `gap_codes` (z. B. `bitget_demo_credentials_incomplete`); entspricht `BITGET_DEMO_ENABLED` und den erwarteten Env-Namen aus [`docs/SECRETS_MATRIX.md`](SECRETS_MATRIX.md).
3. **`llm`:** `llm_use_fake_provider`, `openai_key_present_gateway_env` (nur Anwesenheit im Gateway-Prozess), plus **`orchestrator_probe`** (Auszug aus dem Health des `llm-orchestrator`, u. a. `llm_provider_gap`, `openai_configured`).
4. **`hint_codes`:** konsolidierte Codes fuer Ops; im gleichen Response erscheinen passende Eintraege unter **`warnings`** als `provider:<code>` (z. B. `provider:market_stream_http_429`, `provider:llm_orchestrator_no_provider`).
5. Bei Rate-Limits: **`market-stream`** Logs mit strukturierten Feldern `provider_name`/`provider_event`/`provider_http_status`/`provider_exchange_mode` (keine Secrets); siehe [`docs/PROVIDER_ERROR_SURFACES.md`](PROVIDER_ERROR_SURFACES.md).

## monitor-tick-stalled

1. Prozess `monitor-engine` und Logs `monitor_engine.scheduler`.
2. `GET /health` / `GET /ready` auf 8110; DB- und Redis-Erreichbarkeit.
3. Keine Tick-Inkremente: Histogram `monitor_engine_tick_duration_seconds_count` in Prometheus.

## monitor-tick-slow

1. `histogram_quantile(0.9, rate(monitor_engine_tick_duration_seconds_bucket[10m]))`.
2. Einzelne langsame Service-Probes oder SQL (`refresh_trading_sql_metrics`) isolieren.

## pipeline-lag-p95

1. Metrik `signal_pipeline_lag_p95_seconds_1h` (Feature `computed_ts_ms` vs `analysis_ts_ms`).
2. feature-engine / signal-engine Latenz, Redis-Backpressure, grosse Universen.

## manual-action-misuse

1. `gateway_manual_action_auth_failures_1h`, Detail in `app.gateway_request_audit`.
2. Unterscheidung: falscher Operator-Token vs. Angriff — IPs rotieren, Pfade pruefen.
3. Bei Spike: Kill-Switch erwägen, keine weiteren Releases.

## drift-execution-decisions

1. `execution_drift_or_shadow_decisions_24h`, Stichprobe `live.execution_decisions.decision_reason`.
2. Online-Drift-State, Shadow-Live-Gate, Forensik-Timeline je `execution_id`.

## commerce-billing-auth

1. `commerce_billing_auth_failures_1h`, JWT-Rollen `billing:read` / Gateway-Policy.
2. `docs/commercial_transparency.md` fuer erwartete Header.

## commerce-ledger-spike

1. `commerce_ledger_lines_1h`, Tenant-Gruppierung in SQL.
2. Meter-Secret Rotation, unerwartete `event_type`-Burst.

## redis-stream-lag-critical

1. `redis_stream_lag` > 25000 — sofort Consumer-Health, `XPENDING`, Dead-Letter.
2. Kein automatisches Truncaten ohne Freigabe.

## online-drift-shadow-only

1. `online_drift_action_rank == 2` — Live eingeschraenkt, kein hard_block.
2. Champion/Registry und `learn.online_drift_state.breakdown_json`.

## specialist-disagreement-severe

1. Schwellen > 0.55 (24h-Anteil) — harte Eskalation gegenueber Standard-Alert.
2. Wie `#specialist-disagreement`, plus Stichprobe auf harte Vetos im Adversary-Pfad.

## kill-switch-active

1. Dashboard **Ops** / **Live-Broker**: aktive Scopes, `live.kill_switch_events`.
2. Ursache im `reason` / `source`; kein automatisches Entfernen ohne Freigabe.
3. Nach Behebung: Release-Event laut Runbook Exchange/Broker (kein UI-Shortcut).

## safety-latch

1. Metrik `live_safety_latch_active==1`: Live-Fire gesperrt nach Reconcile-Fail.
2. `live.audit_trails` category `safety_latch`, letztes `action`.
3. Nur nach manuellem Check: dokumentierter Release (siehe Live-Broker-API `safety-latch/release`).

## reconcile-lag

1. Metrik `live_reconcile_age_ms` (Grafana: Trading & Ops).
2. Live-Broker-Logs, letzter `live.reconcile_snapshots` Status.
3. Exchange-REST/WS erreichbar, keine Rate-Limits.

## reconcile-drift

1. `live_reconcile_drift_total` und `details_json.drift` im letzten Snapshot.
2. Orders-only / positions mismatch laut Subcounts — Abgleich Exchange vs. DB.

## shadow-live-gate

1. `shadow_live_gate_blocks_24h`, `shadow_live_match_failures_24h`.
2. `live.execution_decisions` mit `decision_reason=shadow_live_divergence_gate`.
3. Policy `require_shadow_match_before_live` in Reconcile-Details pruefen.

## replay-shadow-divergenz

1. Metrik `shadow_live_assessment_mismatch_24h`, Tabelle `live.shadow_live_assessments` (`match_ok=false`).
2. `report_json` je Assessment fuer Forensik; ggf. Signal-IDs mit Logs (`corr_signal_id`).

## online-drift

1. `online_drift_action_rank` (3 = hard_block): `learn.online_drift_state`, `docs/online_drift.md`.
2. Registry/Champion und `ENABLE_ONLINE_DRIFT_BLOCK` pruefen.

## kritische-audits

1. `live_critical_audits_24h`, Eintraege in `live.audit_trails` severity=critical.
2. Unmittelbare Ursachenanalyse (Exchange, Risk, manuelle Aktionen).

## risk-blocks

1. Metrik `execution_decisions_blocked_24h`, Details in `live.execution_risk_snapshots`.
2. Haeufige `decision_reason`: Limits, Drift, Lane, Truth-Gate — Policy anpassen oder Marktlage.

## router-instability

1. `signal_router_switches_24h` pruefen; hoher Wert bedeutet haeufige Router-Wechsel ueber aufeinanderfolgende Signale.
2. In `app.signals_v1.reasons_json.specialists.router_arbitration` Router-ID, `selected_trade_action` und Gruende fuer betroffene Symbole/TF vergleichen.
3. Ziel ist kein kosmetisches Glätten, sondern Nachvollziehbarkeit: Regime-Flattern, Family-Mismatch oder Playbook-Konflikte identifizieren.

## specialist-disagreement

1. `signal_specialist_disagreement_ratio_24h` pruefen; Dissent kommt aus Adversary, Ensemble-Schrumpfung oder Ueberstimmung zwischen Pre-/Post-Adversary-Aktion.
2. Stichprobe in `docs/signal_engine_end_decision.md` und `app.signals_v1.reasons_json.decision_control_flow`.
3. Nicht Chat/Telegram anpassen, sondern Spezialisten-Logik, Datenkontext oder Regime-Policy.

## data-stale-candles

Siehe [Candle gaps / stale](#candle-gaps--stale) unten; `data_freshness_seconds{datapoint="candles_1m"}`.

## data-stale-signals

1. `data_freshness_seconds{datapoint="signals"}` — letzte Zeile `app.signals_v1`.
2. signal-engine / feature-engine / Redis-Pipeline.

## signal-throughput

1. Bei frischen Kerzen aber `signal_pipeline_throughput_1h < 1`: Filter, Abstention, Modell-Gates.
2. Logs signal-engine; keine Kerzen-Stale gleichzeitig pruefen.

## no-trade-spike

1. `signal_do_not_trade_ratio_1h` plus SQL-Alert `trading:signal_do_not_trade_spike_1h`.
2. Signal-Detail / Explain, `decision_control_flow.no_trade_path`, Online-Drift und Router-Dissent querpruefen.
3. Keine "Freischalten um jeden Preis"-Reaktion: Wenn Marktmechanik/Unsicherheit nicht passt, bleibt `no_trade` korrekt.

## stop-fragility

1. `signal_stop_fragility_p90_24h` plus SQL-Alert `trading:signal_stop_fragility_p90_elevated`.
2. Betroffene Signale auf `stop_distance_pct`, `stop_budget_max_pct_allowed`, `stop_min_executable_pct`, `stop_to_spread_ratio` und `gate_reasons_json` pruefen.
3. Hebel senken oder Universum/Playbook einschränken; keine strukturell unhaltbaren Orders erzwingen.

## llm-dlq

Siehe [LLM / DLQ](#llm--dlq) unten; `data_freshness_seconds{datapoint="llm"}`.

## redis-stream-lag

Siehe [Hoher Redis pending / lag](#hoher-redis-pending--lag).

## order-fail-rate

1. `live_order_fail_rate_1h`, Stichprobe `live.orders` Status error/timed_out.
2. Exchange-Codes in `last_exchange_code` / `order_actions`.

## exit-fehler

1. `live_order_exit_failures_1h` (flatten_failed, error in 1h).
2. Reduzier-Orders, Hedge-Status, manuelle Position auf Boerse.

## learn-drift

1. `learn_drift_events_24h`, Tabelle `learn.drift_events`.
2. Learning-Engine-Run, Champion-Rollback-Policies.

## telegram-delivery

1. `alert_outbox_failed_24h`, `telegram_operator_errors_24h`, `alert_outbox_pending`.
2. `alert.alert_outbox`, `alert.operator_action_audit` und `alert-engine` Logs vergleichen; Zustellung, Upstream-HTTP und Bestätigungsflow trennen.
3. Normale Logs enthalten nur redigierte Chat-Referenzen; tiefe Analyse bei Bedarf ueber Audit-Tabellen mit restriktivem Zugriff.

## alert-backlog

1. `alert_outbox_pending`, `monitor_open_alerts`.
2. alert-engine Zustellung, Telegram/Webhook; `ops.alerts` quittieren.

## auth-anomalies

1. `gateway_auth_failures_1h` und `app.gateway_request_audit action LIKE 'auth_failure_%'`.
2. Pfad, Auth-Methode und betroffene Route (`route_key`) pruefen; unterscheiden zwischen fehlendem Manual-Action-Token, fehlender Auth und Rollenfehlern.
3. Direkte Monitor-OPS-Routen sind intern via `X-Internal-Service-Key` abgesichert; keine offenen Admin-/Ack-Pfade in Production dulden.

## Ueberblick

- **Services**: jeweils `GET /health` (liveness), `GET /ready` (DB/Redis je nach Service), `GET /metrics` (Prometheus, `prometheus_client`).
- **monitor-engine** (Port **8110**): periodischer Run (Standard **10 s**), persistiert Checks in `ops.*`, publiziert bei Problemen **`events:system_alert`** (dedupliziert, Rate-Limit `MONITOR_ALERT_DEDUPE_SEC`).
- **alert-engine** wertet `system_alert`-Events aus Policies aus (Telegram / Outbox).

## Welche Checks laufen?

1. **HTTP**: pro Eintrag in `MONITOR_SERVICE_URLS` werden `/health`, `/ready`, `/metrics` angefragt, Latenz gemessen → `ops.service_checks`.
2. **Redis Streams**: pro Stream in `MONITOR_STREAMS` und jeder existierenden Gruppe aus `MONITOR_STREAM_GROUPS`: `XINFO STREAM`, `XINFO GROUPS`, `XPENDING` → `ops.stream_checks`. Lag: Redis-`lag`, falls `NULL` Heuristik aus `last-generated-id` vs. `last-delivered-id`.
3. **Datenfrische**: `tsdb.candles` (TF `1m`–`4H`, DB-Codes `1H`/`4H`), `app.signals_v1`, `app.drawings` (`updated_ts` → ms), `app.news_items`, `tsdb.funding_rate`, `tsdb.open_interest`, plus LLM/DLQ (`XLEN events:dlq`) → `ops.data_freshness`.
4. **Stream stalled (critical)**: Laenge eines ueberwachten Streams aendert sich nicht **und** `candles_1m` ist **critical** stale.

## Schwellen (Auszug)

| Variable                                                | Bedeutung                                 |
| ------------------------------------------------------- | ----------------------------------------- |
| `THRESH_STALE_MS_*`                                     | Max. Alter letzte Kerze pro TF            |
| `THRESH_STALE_SIGNALS_MS` / `DRAWINGS` / `NEWS` / `LLM` | Frische Signals/Drawings/News/LLM         |
| `THRESH_STALE_FUNDING_MS` / `OI_MS`                     | Funding / Open Interest                   |
| `THRESH_PENDING_MAX` / `THRESH_LAG_MAX`                 | Stream pending / Lag → degraded bzw. fail |
| `THRESH_DLQ_LEN_WARN` / `CRIT`                          | DLQ-Laenge                                |

## Alerts & Quittierung

- Tabelle **`ops.alerts`**: `alert_key` UNIQUE, Zustaende `open` | `acked` | `resolved`.
- Bei erneutem Fehler nach `resolved` wird der State wieder **`open`** gesetzt (Upsert).
- Quittieren: `POST /ops/alerts/{alert_key}/ack` auf monitor-engine — interner Service-Key erforderlich; bei verschachtelten Keys URL-Encoding / Pfad-Parameter `:path` nutzen.
- Event-Payload (`events:system_alert`): `alert_key`, `severity`, `title`, `message`, `details`, `ts_ms`.

## Troubleshooting

### Hoher Redis pending / lag

1. `redis-cli XPENDING <stream> <group>`
2. `redis-cli XINFO GROUPS <stream>`
3. Consumer-Logs pruefen (ACK, Crash). Pending sinkt nur nach **XACK**.

### Candle gaps / stale

1. `SELECT max(start_ts_ms) FROM tsdb.candles WHERE symbol='<example_symbol>' AND timeframe='1m';`
2. market-stream / Bitget-WS pruefen.
3. Fuer Tests: `THRESH_STALE_MS_1M` sehr klein setzen, kurz warten, `ops.alerts` und Redis-Stream `events:system_alert` pruefen.

### LLM / DLQ

1. `redis-cli XLEN events:dlq`
2. Letzte Eintraege `XREVRANGE events:llm_failed + - COUNT 5`
3. `llm-orchestrator` Logs, Circuit-Breaker, Provider-Keys (nicht in Metrics labeln).

## Prometheus / Grafana (optional)

```bash
docker compose --profile observability up -d prometheus grafana
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (Default-Login aus `.env.example` setzen)
- Targets: `infra/observability/prometheus.yml`

Ohne Prometheus bleiben die `/metrics`-Endpoints der Services nutzbar (curl / Debugging).

## Migration

```bash
python infra/migrate.py
psql "$DATABASE_URL" -c "\dt ops.*"
```
