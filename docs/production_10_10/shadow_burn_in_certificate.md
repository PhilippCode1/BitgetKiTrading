# Shadow Burn-in Certificate

## Warum Pflicht

Live-Trading darf erst starten, wenn Shadow ueber mindestens 72 Stunden stabile
Evidence liefert. Der Nachweis muss Multi-Asset-Datenqualitaet,
Reconcile-Failures, P0-Incidents und No-Trade-Gruende sichtbar machen.

## Sicherer Lauf

`scripts/verify_shadow_burn_in.py --dry-run` nutzt keine DB. Mit
`--input-json` kann ein Fixture ohne externe Systeme bewertet werden. Der echte
Run nutzt eine Runtime-Datenquelle und erzeugt einen archivierten Report.

## Keine echten Orders

Das Tool liest nur Shadow-/Audit-/Reconcile-Evidence oder Fixture-Daten. Es
sendet keine Orders.

## Reportfelder

Pflichtfelder sind Git-SHA, Ergebnis, beobachtete Stunden,
Multi-Asset-Datenqualitaet, Reconcile Failures, P0 Incidents, No-Trade-Gruende,
Blocker und Warnings.

## No-Go-Regeln

Weniger als 72 Stunden, P0 Incident, Reconcile-Failure oder fehlende
Multi-Asset-Datenqualitaet blockieren Live.

## Philipp liest den Report

Philipp prueft `Ergebnis`, `Beobachtete Stunden`, Blocker und Warnings. Nur
`PASS` ohne ungeklärte Blocker kann als Burn-in-Evidence fuer Live gelten.
