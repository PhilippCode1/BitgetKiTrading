# Observability (Prometheus / Grafana)

| Artefakt                                      | Zweck                                                           |
| --------------------------------------------- | --------------------------------------------------------------- |
| `prometheus.yml`                              | Scraping der Service-`/metrics`-Endpunkte (Compose-Netz)        |
| `prometheus-alerts.yml`                       | Prometheus-Alert-Regeln (SLIs aus `docs/observability_slos.md`) |
| `grafana/provisioning/`                       | Datasource + Dashboard-Provisioning                             |
| `grafana/dashboards/bitget-trading-ops.json`  | Trading-/Pipeline-Sicht (Frische, Stream-Lag, …)                |
| `grafana/dashboards/bitget-sli-security.json` | SLI Security / Gateway                                          |

**Monitor-Engine-Alerts** (Postgres `ops.alerts`, Redis `events:system_alert`) werden im Code angereichert: siehe `docs/cursor_execution/20_monitor_alerts_and_observability.md` und `services/monitor-engine/src/monitor_engine/alerts/operator_context.py`.

Übergeordnetes Playbook: `OBSERVABILITY_AND_SLOS.md` (Repo-Root).
