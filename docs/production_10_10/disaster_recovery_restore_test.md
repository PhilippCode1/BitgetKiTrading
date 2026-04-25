# Disaster Recovery Restore Test

## Warum Pflicht

Echte Live-Freigabe ist ohne Restore-Nachweis verboten. Backups sind erst dann
Evidence, wenn ein Restore gegen eine Test-/Staging-DB mit RTO/RPO dokumentiert
wurde.

## Sicherer Lauf

`scripts/dr_postgres_restore_test.py --dry-run` kontaktiert keine externen
Systeme und mutiert keine DB. Nicht-dry-run verlangt eine explizite Test-DB-
Bestaetigung mit `--i-understand-this-is-a-test-db`.

## Keine echten Orders

Das Restore-Tool arbeitet nur mit Datenbank-Readiness. Es kann keine Bitget-
Orders senden, canceln oder ersetzen.

## Reportfelder

Der Report enthaelt Datum/Zeit, Git-SHA, redacted Database URL, Status,
Dry-run, RTO Sekunden, RPO Sekunden, Live-ready und klare Aussage, ob echte
Restore-Evidence noch fehlt.

## No-Go-Regeln

Production-DB-URLs werden blockiert. Fehlender echter Restore-Report, fehlende
RTO/RPO-Werte oder nicht archivierte Evidence blockieren Live.

## Philipp liest den Report

Philipp prueft `Status`, `RTO Sekunden`, `RPO Sekunden` und `Live-ready`. Nur ein
separat ausgefuehrter Test-DB-Restore mit akzeptierten RTO/RPO-Werten kann in
die private Live-Freigabe eingehen.
