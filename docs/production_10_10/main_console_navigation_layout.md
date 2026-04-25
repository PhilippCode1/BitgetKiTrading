# Main Console Navigation & Layout

## Kanonische Route

- Hauptstartpunkt der Operator-Oberflaeche: `/console`
- Root `/` wird auf `/console` geleitet.
- Navigation und Layout orientieren sich an einer einzigen Main Console fuer
  Philipp.

## Kanonische Module

1. Uebersicht
2. Assets
3. Charts
4. Signale
5. Risk
6. Broker
7. Sicherheit
8. System
9. Reports
10. Einstellungen

Technische Quelle: `apps/dashboard/src/lib/main-console/navigation.ts`

## Main-Console-Shell

Die Konsole rendert global im Layout:

- Projektkennung `bitget-btc-ai`
- Betriebsmodus-Badge (Local, Paper, Shadow, Staging, Live blockiert, Live bereit)
- Sicherheitsstatus (OK, Warnung, Blockiert)
- Bitget-Verbindungsstatus
- Datenqualitaetsstatus
- Live-Broker-/Reconcile-Status

Implementiert in:

- `apps/dashboard/src/components/layout/MainConsoleStatusBar.tsx`
- eingebunden in `apps/dashboard/src/app/(operator)/console/layout.tsx`

## Verbotene Hauptnavigation

Diese Begriffe/Pfade duerfen nicht Teil der Main-Console-Primärnavigation sein:

- Billing
- Pricing
- Plans
- Customers
- Tenant
- Contracts
- Public-Marketing-Startseiten

## Seitenstruktur je Modul

Jede Modulseite folgt dem Muster:

- klare deutsche Ueberschrift
- Zweck in einem Satz
- Statuskarten und Sicherheitskontext
- naechste sichere Aktion
- deutscher Empty State
- deutscher Error State ohne Secrets
- Link zur passenden Diagnose/Report-Route
