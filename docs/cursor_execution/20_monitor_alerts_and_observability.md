# 20 — Monitor-Engine, Alerts und Observability

## Ziel

**Bessere Bedienbarkeit** ohne weniger Wahrheit: Jeder Alert in `ops.alerts` und jedes `events:system_alert`-Payload soll **strukturiert** machen, was schief laeuft, **wahrscheinliche Ursachen**, **Einstieg im Stack**, **betroffene Dienste** und **Folgewirkung** erkennbar machen. Bezug: **Datei 08** (`docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md`), **SLOs** (`OBSERVABILITY_AND_SLOS.md`, `docs/observability_slos.md`, `docs/observability.md`).

## Architektur (kurz)

| Komponente          | Rolle                                                                                                                                              |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **monitor-engine**  | Periodischer Tick: HTTP-Service-Probes, Redis-Stream-Checks (`XPENDING`, `XINFO`), Datenfrische SQL, Stream-Stall-Heuristik, Trading-SQL-Schwellen |
| **Dedupe DB**       | `ON CONFLICT (alert_key)` auf `ops.alerts` — ein offener Alert pro `alert_key`                                                                     |
| **Dedupe Eventbus** | In-Memory `PublishDedupe` pro `alert_key` fuer `events:system_alert` (Rate-Limit, kein Spam)                                                       |
| **API-Gateway**     | `GET /v1/monitor/alerts/open` → Zeilen aus `ops.alerts` inkl. `details` JSON                                                                       |
| **System-Health**   | Einbettung offener Alerts / Zaehler fuer `warnings_display`                                                                                        |

## alert_key-Schema (Beispiele)

| Muster                        | Familie        | Typische Trigger                                     |
| ----------------------------- | -------------- | ---------------------------------------------------- |
| `svc:<service>:health`        | service_probe  | HTTP nicht ok, Timeout                               |
| `svc:<service>:ready`         | service_probe  | `ready: false` im JSON                               |
| `svc:<service>:metrics`       | service_probe  | `/metrics` nicht 200                                 |
| `svc:live-broker:kill_switch` | service_probe  | SQL/Ops: aktiver Kill-Switch                         |
| `stream:<name>:group:<group>` | redis_stream   | Hohes Pending oder Lag                               |
| `freshness:<datapoint>`       | data_freshness | Kerzen/Signale/News/llm zu alt                       |
| `stream_stalled:<stream>`     | stream_stalled | Stream-Laenge unveraendert + 1m-Kerze kritisch stale |
| `trading:<slug>`              | trading_sql    | Schwellen in `trading_sql_alerts.py`                 |

## Operator-Anreicherung (details-JSON)

Ab **Monitor-Engine**-Version mit `operator_context.py` schreibt `process_alerts` vor jedem `upsert_alert` / `publish_system_alert`:

| Feld                            | Inhalt                                                    |
| ------------------------------- | --------------------------------------------------------- |
| `operator_context_version`      | Schema-Version (aktuell `1`)                              |
| `operator_summary_de`           | Einzeiler                                                 |
| `operator_likely_causes_de`     | Liste kurzer Ursachenhypothesen                           |
| `operator_first_steps_de`       | Konkrete erste Schritte (Kommandos/Pfade)                 |
| `operator_affected_services`    | Liste betroffener Dienste/Cluster                         |
| `operator_stack_entry_de`       | Wo im Stack anfangen                                      |
| `operator_downstream_impact_de` | Erwartete Folgen fuer Pipeline/UI                         |
| `operator_doc_refs`             | Repo-Pfade zu Runbooks                                    |
| `correlation`                   | `alert_key`, `alert_family`, `severity`, `observed_at_ms` |

**Dedupe** bleibt **pro `alert_key`** unveraendert; die Anreicherung aktualisiert sich bei jedem Tick mit aktuellem `observed_at_ms`.

## Nachweise (Abfragen)

**Offene Alerts (Gateway, mit JWT):**

```http
GET /v1/monitor/alerts/open
```

**SQL (Postgres):**

```sql
SELECT alert_key, severity, title, message, details->'operator_summary_de', details->'correlation', updated_ts
FROM ops.alerts
WHERE state = 'open'
ORDER BY updated_ts DESC
LIMIT 20;
```

**System-Health (aggregiert):**

```http
GET /v1/system/health
```

Felder u. a. `ops.monitor.open_alert_count`, `warnings`, `warnings_display`.

### Beispiel `details`-Auszug (schematisch)

Nach Anreicherung enthaelt eine Zeile in `ops.alerts` bzw. die API-Antwort von `/v1/monitor/alerts/open` u. a.:

```json
{
  "operator_context_version": 1,
  "operator_summary_de": "Kurzbeschreibung des Symptoms.",
  "operator_likely_causes_de": ["Ursache A", "Ursache B"],
  "operator_first_steps_de": ["Schritt 1 …", "Schritt 2 …"],
  "operator_affected_services": ["feature-engine", "redis"],
  "operator_stack_entry_de": "Zuerst … pruefen.",
  "operator_downstream_impact_de": "Erwartete Folge …",
  "operator_doc_refs": ["docs/observability_slos.md"],
  "correlation": {
    "alert_key": "freshness:signals",
    "alert_family": "data_freshness",
    "severity": "warning",
    "observed_at_ms": 1743868800000
  }
}
```

Die Basis-Felder des Monitors (z. B. `lag`, `threshold`, Service-URLs) bleiben zusaetzlich erhalten, soweit der jeweilige Alert sie setzt.

**Tests (gesamte Monitor-Suite im Repo):**

```bash
pytest tests/monitor_engine -q
```

(Stand Pruefung: 18 Tests, u. a. Dedupe, Operator-Kontext, Stream-Key-Parsing.)

**Monitor-Engine direkt:**

```http
GET http://monitor-engine:8110/ops/alerts/open
```

## Prometheus / Grafana im Repo

- Regeln: `infra/observability/prometheus-alerts.yml`
- Dashboards: `infra/observability/grafana/dashboards/*.json`
- Kurzüberblick: `infra/observability/README.md`

Prometheus-Alerts ergaenzen die **Monitor-Engine-SQL-Alerts** (andere Schicht, gleiche SLO-Logik laut `docs/observability_slos.md`).

## Offene Punkte

- `[FUTURE]` UI-Konsole: `details.operator_*` explizit als Panel rendern (statt nur Roh-JSON).
- `[FUTURE]` Mehrsprachigkeit: `operator_*_en` optional parallel zu `_de`.
- `[TECHNICAL_DEBT]` Schwere Gewichtung `trading:*` vs. `freshness:*` nur dokumentiert; feinjustierung nach Betrieb.
