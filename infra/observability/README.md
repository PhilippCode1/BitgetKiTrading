# Observability (Prometheus / Grafana)

| Artefakt                                      | Zweck                                                           |
| --------------------------------------------- | --------------------------------------------------------------- |
| `prometheus.yml`                              | Scraping der Service-`/metrics`-Endpunkte (Compose-Netz)        |
| `prometheus-alerts.yml`                       | Prometheus-Alert-Regeln (SLIs aus `docs/observability_slos.md`) |
| `grafana/provisioning/`                       | Datasource + Dashboard-Provisioning                             |
| `grafana/dashboards/bitget-trading-ops.json`  | Trading-/Pipeline-Sicht (Frische, Stream-Lag, …)                |
| `grafana/dashboards/bitget-sli-security.json` | SLI Security / Gateway                                          |
| `alertmanager.yml.example`                    | On-Call-Routing (P0, Reconcile, Safety, Data, LLM) — `tools/verify_alert_routing.py` |
| `alertmanager-inhibit-rules.example.yml`     | Deduplizierung / P0 vor P1                                      |

**Monitor-Engine-Alerts** (Postgres `ops.alerts`, Redis `events:system_alert`) werden im Code angereichert: siehe `docs/observability.md` und `services/monitor-engine/src/monitor_engine/alerts/operator_context.py`.

Übergeordnetes Playbook: `OBSERVABILITY_AND_SLOS.md` (Repo-Root).
