# Observability, SLOs und Betriebs-Playbook

Dieses Dokument ist der **Einstieg fuer Betrieb und On-Call**: welche Ketten zaehlen, welche Messpunkte im Code existieren, welche **SLO-Ziele** realistisch sind, und wie man einen Vorfall **schnell eingrenzt**. Technische Details und Alert-Namen: [`docs/observability.md`](docs/observability.md), SLI-Tabelle: [`docs/observability_slos.md`](docs/observability_slos.md), Prometheus-Regeln: `infra/observability/prometheus-alerts.yml`, Grafana: `infra/observability/grafana/dashboards/`.

---

## 1. Kritische Ketten (was beobachtet werden muss)

| Kette                            | Messpunkte im Betrieb                                                                                                                | Code / Pfad                                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| **Edge-Erreichbarkeit**          | HTTP 200 `GET /health`, `GET /ready` am API-Gateway; `ready: true` und `checks` ohne harte Fehler                                    | `services/api-gateway`                                                                         |
| **Zentraler Lese- und Ops-Pfad** | `GET /v1/system/health` (JWT): `database`, `redis`, eingebettete Worker-/Frische-Felder                                              | Gateway + aggregierte Downstream-Checks                                                        |
| **Pro Worker / Engine**          | Je Dienst `GET /ready` (Postgres/Redis/Peer-URLs laut Settings)                                                                      | z. B. `signal-engine`, `feature-engine`, … `instrument_fastapi` → `/metrics`                   |
| **Datenfluss & Pipeline**        | `data_freshness_seconds`, `redis_stream_lag`, `signal_pipeline_lag_p95_seconds_1h`                                                   | Monitor-Engine-Prometheus, siehe `docs/observability_slos.md`                                  |
| **Hintergrundjobs / Heartbeats** | `worker_heartbeat_timestamp` (von `touch_worker_heartbeat` in HTTP-Middleware und Loops)                                             | `shared_py.observability.metrics`                                                              |
| **KI (Operator Explain)**        | Latenz Gateway→Orchestrator (Logs `llm forward …`), HTTP 5xx-Rate auf `POST /v1/llm/operator/explain`, Orchestrator `/ready` (Redis) | `api_gateway/llm_orchestrator_forward.py`, `llm-orchestrator`, BFF `operator-explain/route.ts` |
| **Fehlerhaeufigkeit**            | `http_request_errors_total` (4xx/5xx je Route-Gruppe), `http_errors_total` (5xx), `http_request_duration_seconds`; Gateway-Audit bei sensiblen Routen | Prometheus pro `/metrics`                                                                 |
| **Pipeline-Verzoegerung / CI**   | (ausserhalb Laufzeit-App) eigene CI-Metriken/Alerts; im Stack: siehe Signal-Pipeline-SLIs                                            | `docs/observability_slos.md`                                                                   |

---

## 2. Messpunkte im Code (keine reine Theorie)

| Mechanismus                     | Wo                                                                                                                                    | Nutzen fuer Operator                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **Request-ID / Correlation-ID** | API-Gateway: Middleware setzt `X-Request-ID`, `X-Correlation-ID`; ausgehend `get_outbound_trace_headers()` z. B. zum LLM-Orchestrator | Gleiche ID in Gateway-Logs und (bei JSON-Log) Felder `corr_request_id`, `corr_correlation_id` |
| **LLM-Orchestrator Trace**      | Middleware setzt Kontext aus eingehenden `X-Request-ID` / `X-Correlation-ID` (abgestimmt mit Gateway)                                 | KI-Aufruf in Logs quer zuordenbar                                                             |
| **Dashboard BFF KI**            | `POST /api/dashboard/llm/operator-explain`: erzeugt oder reicht IDs weiter; Antwort-Header enthalten IDs                              | Browser/DevTools: Response-Header fuer Support-Ticket                                         |
| **Strukturierte Logs**          | `LOG_FORMAT=json` + `RequestContextLoggingFilter`                                                                                     | Log-Shipper kann filtern/aggregieren                                                          |
| **Prometheus**                  | `instrument_fastapi`: Requests, Latenz-Histogramm, 5xx-Zaehler, Heartbeat                                                             | Grafana-Dashboards `bitget-trading-ops`, `bitget-sli-security`                                |
| **Gateway-Audit**               | Persistierte Zeilen mit `corr_gateway_audit_id`                                                                                       | Nachvollziehbarkeit sensibler Aktionen                                                        |
| **Fehler-JSON**                 | Gateway: `shape_http_exception` mit `detail.code` / `message` (ohne Secrets)                                                          | UI und Runbooks koennen Codes mappen                                                          |

---

## 3. Wichtigste SLOs (Zielgroessen)

Die folgenden Ziele sind **technische Orientierung** fuer Alert-Tuning; harte Schwellen liegen in `prometheus-alerts.yml`.

### 3.1 Verfuegbarkeit & Readiness

| SLO                      | Ziel                                                                           | Pruefpfad / Metrik                                       |
| ------------------------ | ------------------------------------------------------------------------------ | -------------------------------------------------------- |
| **Gateway lebend**       | 99,5 % Zeit HTTP 200 auf `/health` (oder Ihre SLA)                             | Blackbox oder LB-Health                                  |
| **Stack „bereit“**       | `GET /ready` am Gateway: `ready: true` unter Normalbedingungen                 | Alle eingetragenen `HEALTH_URL_*` / interne Checks gruen |
| **Auth-Pfad konsistent** | Kein anhaltender Anstieg 401/403 auf `GET /v1/system/health` bei gueltigem JWT | `gateway_auth_failures_*` / manuelle Stichprobe          |

### 3.2 Zentrale Lesepfade (Beispiel)

| SLO                            | Ziel                                                    | Hinweis                                                        |
| ------------------------------ | ------------------------------------------------------- | -------------------------------------------------------------- |
| **System-Health Latenz**       | p95 < 3 s unter Last (anpassen)                         | Histogram am Gateway; bei Timeout Runbook: DB/Redis/Downstream |
| **API p95 je kritische Route** | Team-spezifisch; Startwert p95 < 5 s fuer Standard-GETs | `http_request_duration_seconds` (Labels `service`, `http_route`) |

### 3.3 Datenfrische & Pipeline

| SLO                     | Ziel                            | Quelle                               |
| ----------------------- | ------------------------------- | ------------------------------------ |
| Kerzen 1m               | Staleness < 180 s               | `docs/observability_slos.md`         |
| Signale                 | Staleness < 300 s               | wie oben                             |
| Stream-Lag              | < 5k (Warn) / < 25k (kritisch)  | `redis_stream_lag`                   |
| Feature→Signal-Pipeline | P95 < 180 s wenn Daten anliegen | `signal_pipeline_lag_p95_seconds_1h` |

### 3.4 KI (Operator Explain)

| SLO                                   | Ziel                                                  | Begruendung                                                     |
| ------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------- |
| **Erfolgsrate**                       | > 99 % HTTP 2xx unter Normalbetrieb (ohne Rate-Limit) | Excludes: absichtlich zu grosse Prompts, fehlender Provider-Key |
| **Latenz (e2e Gateway-Orchestrator)** | p95 < 90 s, p99 < 120 s                               | OpenAI/Netz variabel; Timeout Gateway 120 s                     |
| **Orchestrator Redis**                | `/ready` Redis-Check gruen                            | Cache/Circuit; ohne Redis kein stabiler Betrieb                 |

### 3.5 Live-Ausfuehrung (Auszug)

| SLO               | Ziel    |
| ----------------- | ------- |
| Kill-Switch       | 0 aktiv |
| Reconcile-Alter   | < 90 s  |
| Order-Failrate 1h | < 15 %  |

Vollstaendige SLI-Liste: **`docs/observability_slos.md`**.

---

## 4. Alerts und Eskalation (Muster)

### 4.0 P0-Blocker (Seite/Notruf) vs. P1

| Prioritaet | Label in den Regeln | Beispiel-Namen in `prometheus-alerts.yml` | Typische Reaktion |
| ---------- | -------------------- | ------------------------------------------- | ----------------- |
| **P0**     | `alert_tier: p0`, `severity: critical` | `GatewayHighErrorRate`, `LiveBrokerDegraded`, `MarketStreamLag` | Sofort, On-Call, Runbook oeffnen |
| **P1**     | meist `severity: warning` (ohne p0)    | `RedisStreamLagHigh`, `DataStaleSignals`, … | Reaktion im Dienst, Gruppierung im Alertmanager |

P0-Regeln stehen in der Gruppe `p0_production_blocker`; alle weiteren `groups` sind fachlich P1/P2 – die Dringlichkeit ergibt sich aus `severity: critical` vs. `warning` und eurer Alertmanager-Route.

1. **Quelle:** Prometheus-Regeln unter `infra/observability/prometheus-alerts.yml` (P0 oben, danach u. a. `DataStaleCandles1m`, `RedisStreamLagCritical`, …).
2. **Routing (Slack / PagerDuty):** In **alertmanager.yml** (nicht im Anwendungsrepo) **Receiver** definieren und an **route** haengen. Typisches Muster:
   - **PagerDuty (kritische Seite):** In PagerDuty eine **Services**-Integration anlegen (Events **v2** API) und **Integration Key** (Routing Key) oder globale **Events API**-URL kopieren. In Alertmanager einen `receiver` mit `pagerduty_configs` anlegen, z. B. `service_key: '<from-pagerduty>'` bzw. `routing_key` je nach API-Version, und eine **Sub-Route** mit `matchers: [ alert_tier = "p0" ]` oder `severity = "critical"`, damit nur produktionskritische Alerts seiten. Allgemeinere `warning`-Alerts in einen zweiten Receiver (Slack) routen.
   - **Slack:** In Slack einen **Incoming Webhook** (oder die neuere App mit OAuth) erzeugen; in Alertmanager `slack_configs` mit `api_url: '<webhook-url>'` und sinnvollem `channel` bzw. `title` / `text` setzen. Optional **separate** `route`-Knoten: z. B. `match: alert_tier: p0` → dedizierter High-Priority-Kanal, `severity: warning` → Team-Kanal. **Hinweis:** Webhook-URLs und Keys nur aus Secret-Store (Kubernetes Secret, Vault) beziehen, **nicht** im Git ablegen.
   - **Inhibit-Regeln:** `infra/observability/alertmanager-inhibit-rules.example.yml` in eure `inhibit_rules` mergen, damit P0- und Folge-Alarme nicht doppelt fluten (z. B. `LiveBrokerDegraded` vs. `ReconcileLagHigh` bei gleicher `category`).
3. **Eskalation (empfohlen):**
   - **L1 (15 min):** Pruefung `GET /ready` Gateway, `GET /v1/system/health` mit gueltigem JWT, letzte Deploys.
   - **L2:** Engpass-Service anhand `checks` und Metrik-Label; Log-Zeilen mit `corr_request_id` zum Vorfallzeitpunkt.
   - **L3:** Datenbank/Redis/Infrastructure-Team bei persistierendem DB/Redis-Down.

**Runbook pro Alert:** Kurz beschreiben: _Symptom → erste Query → haeufige Ursache → Rollback/Restart-Freigabe._

---

## 5. Fehlerfall schnell eingrenzen (Operator-Playbook)

### Schritt A: Was ist kaputt?

- **Browser/Operator:** Dashboard-Fehlermeldung notieren (oft `detail.code`).
- **Gateway:** `X-Request-ID` aus Response-Header (KI: auch nach BFF-Antwort).
- **Globale Sicht:** Grafana: Spike bei `http_request_errors_total` (5xx) bzw. `http_errors_total` oder spezifischen Gauges (Freshness, Lag).

### Schritt B: Wo ist es kaputt?

| Symptom                    | Naechster Check                                                           |
| -------------------------- | ------------------------------------------------------------------------- |
| 502/503 vom Dashboard-BFF  | `API_GATEWAY_URL`, Gateway-Logs, `edge-status` JSON                       |
| 503 `LLM_ORCH_UNAVAILABLE` | Gateway: `LLM_ORCH_BASE_URL`, `INTERNAL_API_KEY`; Orchestrator erreichbar |
| 502 LLM / Provider         | Orchestrator-Logs: OpenAI-Key, `LLM_USE_FAKE_PROVIDER`, Schema-Validation |
| `/ready: false`            | JSON `checks` — welcher Service-URL oder Postgres/Redis rot               |
| Daten „alt“                | `data_freshness_seconds` / Alerts `DataStale*`                            |

### Schritt C: Seit wann?

- Grafana-Zeitreihe zum Metriknamen; Logs nach `corr_request_id` oder Zeitstempel filtern.
- Gateway-Audit-Tabelle (wenn aktiviert) fuer mutierende Pfade.

### Schritt D: Wie stark die Wirkung?

- **Nur KI-Hilfe down:** Trading kann weiterlaufen — Kommunikation: eingeschraenkter Operator-Support.
- **Gateway /ready false:** haengende oder fehlende Datenstroeme — **hoch**.
- **Kill-Switch / Safety:** **kritisch** — sofortiges Runbook „Live“.

---

## 6. Dashboards und Pruefpfade (Checkliste)

| Aufgabe           | Aktion                                                                                                      |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| Taeglicher Health | `curl -sS "$API_GATEWAY_URL/ready" \| jq .`                                                                 |
| Auth + Datenlage  | `curl -sS -H "Authorization: Bearer …" "$API_GATEWAY_URL/v1/system/health" \| jq .warnings,.data_freshness` |
| KI-Smoke          | `python scripts/staging_smoke.py --env-file .env.shadow` oder `AI_FLOW.md`                                  |
| Metriken scrape   | Pro Service `GET http://<service>:<port>/metrics` (nicht oeffentlich exponieren ohne Schutz)                |

---

## 7. Aenderungen in diesem Repo (Referenz)

- **Neu / verbessert:** Explizite Logzeilen im LLM-Gateway-Forward (Dauer, Pfad, Hinweis bei HTTP-Fehler).
- **Neu:** Trace-Middleware im **llm-orchestrator** (Korrelation mit Gateway).
- **Neu:** **BFF** `operator-explain` reicht `X-Request-ID` / `X-Correlation-ID` und gibt sie zurueck.
- **Erweitert (Prompt 23):** Zentrale Trace-Header fuer praktisch alle `fetchGatewayUpstream`-Aufrufe; strukturierte `corr_*`-Felder im LLM-Forward-Log; `edge-status` liefert `supportReference` pro Diagnose-Lauf; Beispiel **Alertmanager inhibit_rules** unter `infra/observability/alertmanager-inhibit-rules.example.yml`; Prometheus-Regeln leicht entschaerft/annotiert (DataStaleSignals, Shadow-Live-Gate, Alert-Backlog).
- **Monitor-Engine:** `ops.alerts.details` und `events:system_alert` enthalten strukturierte Betreiberfelder (`operator_*`, `correlation`) — `docs/cursor_execution/20_monitor_alerts_and_observability.md`.

Aeltere Basis: `docs/observability.md`, `docs/observability_slos.md`, `shared_py.observability`, Gateway-Request-ID-Middleware.
