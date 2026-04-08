-- NUR lokale Entwicklung: ALLE ops.alerts mit state=open auf resolved setzen.
-- In Production oder Shadow NIEMALS ohne Ursachenanalyse ausfuehren.
--
-- Typischer Anwendungsfall: nach erstem Stack-Start stapeln sich viele Alerts
-- (z. B. Kerzen/News noch nicht gefuellt, Live-Broker oeffentliche Probe) —
-- Dashboard zeigt „46 offene Alerts“. Nach Pruefung der Logs ausfuehren.
--
-- Ausfuehrung: pnpm alerts:close-local-all
--   (intern: -Scope AllOpen -Force; Produktions-ENV wird vom Skript abgelehnt)

UPDATE ops.alerts
SET state = 'resolved', updated_ts = now()
WHERE state = 'open';
