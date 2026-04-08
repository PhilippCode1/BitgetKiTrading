# Incident- & Recovery-Runbooks (Sicherheit, Geld, Vertrauen)

Ergänzung zu `docs/monitoring_runbook.md` (Prometheus-Alert-Anker). Fokus: **schnelle Eindämmung**, **Beweissicherung**, **geordnete Wiederaufnahme**.

## Kill-Switch aktiv

1. **Ziel:** Jegliche automatisierte Live-Feuer stoppen, Zustand dokumentieren.
2. **Pruefen:** `live.kill_switch_events`, `live_kill_switch_active_count`, Operator-Dashboard Live-Broker.
3. **Kommunizieren:** Incident-Channel; keine heimlichen Deaktivierungen.
4. **Recovery:** Ursache beheben (Exchange, Bug, Policy), dann kontrolliertes Release laut Exchange/Broker-Runbook — **nicht** nur Metrik auf 0 drücken.

## Safety-Latch (Post-Reconcile-Fail)

1. **Symptom:** `live_safety_latch_active == 1`, Live-Fire blockiert.
2. **Forensik:** `live.audit_trails` category `safety_latch`, letzter Reconcile-Snapshot `details_json.drift`.
3. **Recovery:** Manuelle Abstimmung Ops/Risk; API `safety-latch/release` nur mit dokumentierter Checkliste (Positionen, Orders, Exchange-Truth).

## Emergency Flatten

1. **Wann:** unkontrollierbares Marktrisiko, Exchange-Desync, oder Sicherheitsvorfall mit offenen Positionen.
2. **Schritte:** Reduce-only / Flatten ueber Live-Broker-Pfade (autorisierte Rollen), parallel **keine** neuen Entries.
3. **Nachweis:** Jede Order mit `internal_order_id` / `execution_id` in Logs und `live.orders`; Screenshots nur sekundär, DB ist primaer.

## Stale Data (Kerzen/Signale)

1. **Erkennung:** `DataStaleCandles1m`, `DataStaleSignals`, `SignalThroughputStalled`.
2. **Eindämmung:** Signal-Engine kann Abstention erhoehen — **kein** Gegensteuern durch Risikoerhoehung.
3. **Recovery:** market-stream / Bitget-WS, ggf. Symbol-Subset; nach Wiederherstellung Frische in Grafana verifizieren.

## Gateway-Kompromittierung (vermutet)

1. **Indikatoren:** `GatewayAuthAnomalies`, `ManualLiveBrokerAuthFailures`, ungewoehnliche `gateway_request_audit`-Pfade von neuen IPs.
2. **Eindämmung:** API-Keys/JWT rotieren, betroffene Rollen sperren, **Kill-Switch** in Betracht ziehen.
3. **Forensik:** Alle Zeilen mit `corr_gateway_audit_id` aus Logs mit DB `app.gateway_request_audit` joinen.
4. **Recovery:** Nur nach Threat-Assessment; erneute Pen-Tests auf Admin-/Mutation-Pfade.

## Model Drift / Online-Drift-Block

1. **Symptome:** `OnlineDriftHardBlock`, `OnlineDriftShadowOnly`, `LearnDriftEventsSpike`.
2. **Operativ:** Keine Champion-Promotion; Paper/Shadow bevorzugt.
3. **Recovery:** Learning-Engine, Registry-Slots, `learn.online_drift_state` — siehe `docs/online_drift.md`.

## Billing / Usage-Missbrauch

1. **Symptome:** `CommerceLedgerWriteSpike`, `CommerceBillingAuthFailures`, unplausible `usage_ledger`-Tenant-Spikes.
2. **Schritte:** `commercial_meter_secret` rotieren; Tenant-Limits in `tenant_commercial_state`; Gateway-Audit zu `/v1/commerce/*`.
3. **Rechtliches:** Keine Kunden-Personendaten in Metrik-Labels; Auswertung aggregiert.

## Queue-Notstand (Redis)

1. **Symptom:** `RedisStreamLagCritical` oder wachsendes `XPENDING`.
2. **Schritte:** Consumer skalieren/restart **nur** idempotent; keine `DEL` auf Streams ohne Freigabe.
3. **Verifikation:** Lag-Zeitreihe und `events:system_alert` quittieren.

## Verknuepfung Forensik ↔ Metriken

- Pro Live-Vorfall: `execution_id` aus Alert oder UI → **Forensic-Timeline** abrufen.
- Phasen: `forensic_phases.indices_by_phase` + `signal_path_summary` (Spezialisten/Router/DCF kompakt).
- Korrelation: `correlation.correlation_chain.signal_id` / `upstream_event_id` fuer Rueckverfolgung in Logs (`corr_*`).
