# Main Console UX Finalisierung

## Ziel

Die Main Console ist die zentrale, deutsche, private Arbeitsoberflaeche fuer
Philipp. Keine kaputten Seiten, keine verwirrende Navigation, keine toten
Marketing-/Customer-/Billing-Pfade in der aktiven Hauptnutzung.

## Routeninventar

Das UX-Audit (`scripts/main_console_ux_audit.py`) inventarisiert:

- bekannte `/console/...` Routen
- Navigationseintraege aus `lib/main-console/navigation.ts`
- potenziell tote Routen ohne Main-Console-Anbindung
- Billing/Customer/Pricing/SaaS-Routen als Restbestand
- fehlende Empty-/Error-State-Guards (statisch)

## Navigation-Bereinigung

- Aktive Main-Console-Navigation bleibt zentral in `navigation.ts`.
- Deutsche Labels sind Pflicht fuer Hauptnavigation.
- Legacy-/historische Customer/Billing-Bereiche werden nicht als Main-Console-
  Kern empfohlen und im Audit sichtbar gemacht.

## Tote oder unklare Seiten

- Routen ohne Navigation oder ohne stabile States werden als unklar markiert.
- Nicht fertig verdrahtete Seiten werden als "noch nicht verbunden" mit
  deutschem blockierendem Hinweis behandelt statt still leer.

## Main-Console-Bereiche

Finale UX-Informationsarchitektur umfasst mindestens:

1. Uebersicht
2. Asset-Universum
3. Charts & Markt
4. Signale & Strategien
5. Risk & Portfolio
6. Live-Broker
7. Sicherheitszentrale
8. Incidents & Health
9. Reports & Evidence
10. Einstellungen

## Empty-State Pflicht

Jede aktive Seite braucht einen sicheren Empty State:

- klare deutsche Erklaerung
- Datenquelle/Fehlersituation
- naechster sicherer Schritt
- keine gruene Fake-Entwarnung bei unknown/missing data

## Error-State Pflicht

Jede aktive Seite braucht einen redacted Error State:

- deutsche Fehlermeldung
- keine Secrets
- Hinweis, ob Live dadurch blockiert ist

## Sicherheitszentrale und Asset-Universum

Die Routen `/console/safety-center` und `/console/market-universe` sind als
Pflichtbereiche in der Main Console eingeplant und werden im UX-Audit als
P0-relevant geprueft.

## Manuelle Browser-Pruefung

Nach statischem Audit bleiben manuelle E2E-Pruefungen notwendig:

- Mobile Sichtbarkeit kritischer Banner
- Routing-Rueckwege (ReturnTo/Auth/Welcome)
- Fokus-/Kontrast-/Interaktionsklarheit pro Hauptseite
- echte Backend-Ausfaelle: bleibt UX verstaendlich und fail-closed?
