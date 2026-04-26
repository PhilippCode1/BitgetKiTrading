# Observability and Alert-Routing Evidence Report

## Zusammenfassung

- Erzeugt: `2026-04-25T23:32:39Z`
- Git SHA: `84d7b66`
- Doku vollstaendig: `True`
- Alertmanager/Prometheus-Check: `PASS`
- Alert-Drill-JSON (strict): `False`
- Ops/SLO-JSON: `FAIL`
- Interne Issues: `0`

## Alertmanager / Prometheus (repo)

- - Keine Befunde.

## Alert-Zustellung (evidence json)

- assess_delivery_evidence: `FAIL`
- Warnings: ['owner_signoff_missing_external_required']

## Observability-Ops-Template

- Status: `FAIL`
- `status_nicht_verified`
- `reviewed_by_fehlt_oder_template`
- `reviewed_at_fehlt_oder_template`
- `environment_fehlt_oder_template`
- `git_sha_fehlt_oder_template`
- `grafana_ops_dashboard_uri_fehlt`
- `grafana_sli_dashboard_uri_fehlt`
- `grafana_baseline_nicht_belegt`
- `slo_gateway_fehlt`
- `slo_system_health_p95_fehlt`
- `slo_data_freshness_fehlt`
- `slo_live_safety_fehlt`
- `on_call_nicht_dokumentiert`
- `runbook_peer_review_fehlt`
- `incident_drill_ref_fehlt`
- `owner_signoff_fehlt`

## Interne Issues

- `-`

## Erforderlich extern

- Staging-/Shadow-Alert-Drill mit Zustellnachweis: siehe alert_routing_evidence.template.json und verify_alert_routing --evidence-json.
- Grafana/SLI-Baseline und SLO-Betriebsreview: siehe observability_slos_evidence.template.json.
- Owner-Signoff fuer On-Call-Pfad und Incident-Response vor privatem Live-Go.

## Empfohlene Kommandos

- `python tools/verify_alert_routing.py --strict`
- `python tools/verify_alert_routing.py --evidence-json docs/production_10_10/alert_routing_evidence.template.json --strict`
- `pytest tests/unit/monitor_engine -q`

## Einordnung

- Dieser Report fasst repo-lokale Pruefungen zusammen; kein Ersatz fuer echte Staging-Metrik-Baselines.
- private_live_allowed bleibt NO_GO bis verified externe Evidence und Matrix-Kategorien verified sind.
