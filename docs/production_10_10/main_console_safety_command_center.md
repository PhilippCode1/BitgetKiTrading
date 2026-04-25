# Main Console Sicherheitszentrale

## Ziel

Eine einzige deutsche Sicherheitszentrale in der Main Console fuer Philipp:
Status, Blockgründe und Notfallpfade auf einen Blick.

## Sicherheitskarten

1. Systemmodus (`local`, `paper`, `shadow`, `staging`, `live`)
2. Live-Trading-Status (deaktiviert, vorbereitet, blockiert, freigegeben, pausiert)
3. Kill-Switch-Status
4. Safety-Latch-Status
5. Reconcile-Status
6. Exchange-Truth
7. Bitget-Readiness
8. Asset-Freigabe (chart-/shadow-/live-fähig, blockiert)
9. Notfallaktionen (Live-Pause, Kill-Switch, Cancel-All-Simulation, Emergency-Flatten reduce-only)
10. Aktuelle No-Go-Gründe auf Deutsch

## Harte UI-Regeln

- Unknown in kritischen Zuständen zeigt zwingend "Live blockiert".
- Keine direkte echte Order-Aktion aus der UI ohne sichere Backend-Gates.
- Gefährliche Aktionen nur mit Bestätigung, Modus-Hinweis und Audit-Hinweis.
- Fehlende Backend-Daten sind "nicht verbunden"/"nicht geprüft", nie grün.
- Keine Secrets oder Schlüssel in Karten/Logs.

## Main-Console-Anbindung

Navigationseintrag in der Hauptnavigation:
`/console/safety-center` mit deutschem Label `Sicherheitszentrale`.

## Bekannte Grenzen

Falls sichere Mutationsendpunkte fehlen, bleiben Aktionen in read-only/simuliertem
Zustand und dokumentieren den Blocker.

## Referenzen

- `docs/live_broker.md`
- `docs/emergency_runbook.md`
- `docs/production_10_10/live_broker_multi_asset_preflight.md`
