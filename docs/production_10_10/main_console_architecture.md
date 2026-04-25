# Main Console Architecture (Masterplan)

## Zielbild

`bitget-btc-ai` ist eine private, deutsche Single-Owner-Anwendung fuer Philipp.
Die sichtbare Produktstruktur wird auf **eine zentrale Main Console**
ausgerichtet. Keine aktive Verkaufs-, Billing-, Customer-, Tenant- oder
SaaS-Navigation in der Hauptoberflaeche.

## Verbotene und erlaubte Begriffe

### Verboten in aktiver Hauptnavigation

- Billing
- Customer
- Tenant
- Pricing
- Plans
- Subscribe
- Contract
- Sales
- Public Launch

### Erlaubt in aktiver Hauptnavigation

- Konsole
- Assets
- Charts
- Signale
- Risk
- Broker
- Sicherheit
- Shadow
- Paper
- Readiness
- Reports
- Systemstatus

## Verbindliche Top-Level-Module

1. Uebersicht
2. Asset-Universum
3. Charts
4. Signale und KI-Erklaerung
5. Risk und Portfolio
6. Paper/Shadow/Live-Readiness
7. Live-Broker und Execution-Safety
8. Systemstatus und Alerts
9. Reports und Evidence
10. Einstellungen und Runtime-Checks

## Main-Console-Routen (behalten)

- `/console`
- `/console/market-universe`
- `/console/terminal`
- `/console/signals`
- `/console/ops`
- `/console/shadow-live`
- `/console/live-broker`
- `/console/safety-center`
- `/console/incidents`
- `/console/usage`
- `/console/account/language`

## Routenklassifikation (Masterplan)

- `behalten_main_console`
  - aktive Kernroute der Main Console
- `intern_ops_only`
  - technisch benoetigt, aber nicht prominent
- `deprecated_internal`
  - Legacy/Customer/Billing/Commerce-Reste, nicht ausbauen
- `technisch_benoetigt_nicht_prominent`
  - derzeit noetig, aber nicht als Kernmodul bewerben

## API/BFF-Routen

- `/api/dashboard/gateway/*` und operatorische API-Pfade bleiben zentrale BFF-
  Schnittstelle.
- Commerce-/Customer-BFF-Routen sind Legacy und nicht Teil der Main-Console-
  Zielarchitektur.

## Welcome-/Entry-Regel

Falls `/welcome` genutzt wird, bleibt es eine kurze deutsche Einstiegsschleuse
ohne Marketinglogik und fuehrt sinnvoll in die Main Console.

## Umsetzungsregel

- Technisch benoetigte Legacy-Bereiche werden nicht blind geloescht.
- Sie werden aus Hauptnavigation entfernt/versteckt und als deprecated/internal
  dokumentiert.
- Kaputte oder unverbundene Seiten muessen stattdessen sichtbare deutsche
  Blockhinweise und sichere naechste Schritte zeigen.
