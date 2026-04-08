-- Nur fuer lokale Entwicklung / nach Pruefung: offene ops.alerts schliessen.
-- VORSICHT: In Production nur nach Ursachenanalyse ausfuehren.
--
-- Ausfuehrung: pwsh scripts/close_local_monitor_alerts.ps1
-- Alle open auf einmal (nur Dev): scripts/sql/close_open_monitor_alerts_local_all.sql
--   bzw. pwsh scripts/close_local_monitor_alerts.ps1 -Scope AllOpen
--
-- Variante A: alle offenen Alerts (aggressiv)
-- UPDATE ops.alerts SET state = 'resolved', updated_ts = now() WHERE state = 'open';
--
-- Variante B: typischer Laerm durch Bitget-Public-Probe ohne gueltige API (ein Schluessel)
UPDATE ops.alerts
SET state = 'resolved', updated_ts = now()
WHERE state = 'open'
  AND alert_key = 'live-broker:execution-guard:public_probe_fail';

-- Weitere bekannte Schluessel bei Bedarf ergaenzen, z. B.:
-- AND alert_key LIKE 'live-broker:%'
