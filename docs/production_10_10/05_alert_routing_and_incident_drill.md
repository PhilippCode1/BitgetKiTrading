# Alert-Routing, On-Call und Incident-Drill

## Vertragsdateien (Repo)

- `infra/observability/alertmanager.yml.example` — Routing, Receiver, Platzhalter (`${ALERTMANAGER_*}`)
- `infra/observability/prometheus-alerts.yml` — Regeln, `labels.severity` / `alert_tier: p0`, `annotations.runbook`
- `infra/observability/alertmanager-inhibit-rules.example.yml` — Deduplication / Unterdrückung
- Werkzeug: `tools/verify_alert_routing.py`

## Kritische Routen (Mindestbild)

| Thema | Indikator in Beispiel-AM-Config | Prometheus-Quelle (Auszug) |
|--------|----------------------------------|-----------------------------|
| P0 / global trading halt | `alert_tier = p0`, `SafetyLatchActive` | `p0_production_blocker`, `SafetyLatchActive` |
| Live-Broker / Reconcile | `alertname =~ Reconcile.*` | `ReconcileLagHigh`, `ReconcileDriftNonZero` |
| Kill-Switch | `KillSwitchActive` | `KillSwitchActive` |
| Stale market | `MarketPipelineLag`, `DataStale*` | `MarketPipelineLag`, `DataStaleCandles1m` |
| Gateway-Auth | `GatewayAuthAnomalies` | `GatewayAuthAnomalies` |
| DB/Redis/Stack (Proxy) | `RedisStream*`, `LLMPipeline*`, `MonitorEngine*` | Stream-Lag, LLM-Pipeline, Monitor-Tick |
| LLM-Operator | `LlmHigh*` | `LlmHighErrorRate`, `LlmHighLatency` |

Echte `up{}`-Alarme für einzelne Stores können später ergänzt werden; die Route `infra_data_stack` bündelt bis dahin **kritische** Infra-Signale aus dem bestehenden Regelwerk.

## Testalarm

1. **Staging-Alertmanager** mit `test_only`-Route (`test_alert=true` am Alert) **oder** `amtool` gegen die Staging-API.
2. Kein Feuern in Prod ohne Change-Fenster; Label `test_alert=true` in Prometheus-`amtool`/`POST /api/v1/alerts` setzen.
3. Verifikation, dass **Receiver** (Slack-Testkanal) eine Nachricht erhält; P0-Tests nur mit Freigabe.

**Dry-Run:** `python tools/verify_alert_routing.py --config ... --dry-run` (nur YAML-Parse).

## On-Call / Verantwortung

- **P0 / Safety:** laut Roster (extern) — in der Regel: Trading + SRE; **PagerDuty/Phone** via `pagerduty_configs` am P0-Receiver, nicht nur Chat.
- **P1:** Slack-Kanäle pro Lane (Trading, Data, Sec, LLM) gemäß `receivers` in der deployten Config.
- **Eskalation** und Dienst-Roster: Betriebsdokumentation (nicht im Klon ersetzbar); hier nur technischer Routing-Vertrag.

## Zeitziele (Orientierung)

- **P0 bestätigen:** &lt; 15 min bis erste menschliche Reaktion (Organisationsziel, Messung in Incident-Tool).
- **Reconcile / Kill-Switch:** sofort Sichtbarkeit in Primärkanal (kein nur-email-default für P0).

## Incident-Drill: Dokumentation (PASS-Definition)

1. Szenario wählen (z. B. simulierter P0-Alert oder Test-Route in Staging).
2. Durchführen: Quittierung im Kanal, Rückfrage an On-Call laut Playbook, **Zeitstempel UTC**, Teilnehmer.
3. Abnahme-Datei: Kurzprotokoll + Screenshot/Link (Ticket), **kein Secret** in Repo.
4. **PASS** für L4-Readiness: mindestens ein **archivierter** Drill in Staging/äquivalent mit **nachvollziehbarem** Zustell-Nachweis; **reines** Doku-OK reicht die Ampel nicht (siehe Gap-Register).

## Werkzeug-Aufruf

```bash
python tools/verify_alert_routing.py --config infra/observability/alertmanager.yml.example --report-md /tmp/alert_routing.md --strict
```

- Exit **0**: Struktur-`PASS` (lokal ohne echte Webhooks).
- Echte Pager/Slack-Produktivität = **externe** Evidenz (`BLOCKED_EXTERNAL` bis Drill vorliegt).
