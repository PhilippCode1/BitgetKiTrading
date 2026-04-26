# Observability Alert Incident Guide

## Kritische Alerts

Mindestens kritisch: Live-Broker down, API-Gateway down, Market-Data stale,
Reconcile-Drift, Safety-Latch aktiv, Kill-Switch aktiv, Bitget Auth/Permission,
Redis/Postgres unavailable, Backup/Restore failure, Shadow/Live divergence.

## Erforderliche Kanaele

P0 muss in einen echten Operator-Kanal mit Mensch-Quittierung routen
(z. B. Slack + PagerDuty). Dummy-Kanaele zaehlen nicht als verified.

## Alert-Zustellung testen

```bash
python tools/verify_alert_routing.py --strict --report-md reports/alert_routing_verify.md
python tools/verify_alert_routing.py --evidence-json docs/production_10_10/alert_routing_evidence.template.json --strict --strict-external
```

## Incident-Drill

```bash
python scripts/incident_drill_report.py --output-md reports/incident_drill.md --output-json reports/incident_drill.json
```

Ohne echte Zustellung bleibt der Drill synthetisch und nicht verified.

## Benoetigte SLO/SLI-Baselines

- Gateway availability/error budget
- System health latency budget
- Data freshness budget
- Live safety exposure/go-no-go budget

## Entstehende Reports

- `reports/alert_routing_verify.md`
- `reports/observability_alert_evidence.md`
- `reports/observability_alert_evidence.json`
- `reports/incident_drill.md`
- `reports/incident_drill.json`

## Wann `alert_routing` verified sein darf

Nur mit echtem Zustellnachweis, Ack-Latenz, dedupe proof, runbook proof und
Owner-Review.

## Wann `observability_slos` verified sein darf

Nur mit echter SLI/SLO-Baseline, Runtime-Evidence und Owner-Review.

## Warum ohne Evidence NO_GO

Ohne echte Alert-/SLO-/Incident-Evidence kann Philipp kritische Live-Risiken
nicht institutionell sicher erkennen und steuern; daher bleibt Live `NO_GO`.
