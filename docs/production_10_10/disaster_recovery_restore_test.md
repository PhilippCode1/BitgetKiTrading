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

## Externer Restore-/DR-Evidence-Contract

`scripts/dr_postgres_restore_test.py` kann neben dem sicheren Dry-run auch ein
secret-freies JSON mit echter Restore-/DR-Evidence pruefen:

```bash
python scripts/dr_postgres_restore_test.py \
  --evidence-json docs/production_10_10/postgres_restore_evidence.template.json \
  --strict \
  --output-md reports/postgres_restore_evidence.md
```

Das Repo-Template bleibt absichtlich `FAIL`, bis ein echter Staging-/Clone-
Restore belegt ist. Fuer Live-Evidence muessen mindestens diese Punkte auf
`PASS` bzw. `true` stehen:

- Backup-Label und Backup-Artefakt-SHA256
- verschluesselte Backup-Ablage
- Restore-Status `PASS`
- Git-SHA und Restore-Ziel
- RTO/RPO innerhalb Budget
- Checksumme verifiziert
- Migration-Smoke bestanden
- Live-Broker-Read-Smoke bestanden
- Reconcile-State validiert
- Audit-Trail wiederhergestellt
- Safety-Latch nach Restore default-blocked
- Alert-Route verifiziert
- externer Review mit Evidence-Referenz
- Owner-Signoff separat vorhanden

Felder mit Secret-Bezug wie `database_url`, `dsn`, `password`, `secret`, `token`
oder `api_key` duerfen keine echten Werte enthalten. Erlaubt sind nur
`[REDACTED]`, `REDACTED`, `not_stored_in_repo` oder leer.

## No-Go-Regeln

Production-DB-URLs werden blockiert. Fehlender echter Restore-Report, fehlende
RTO/RPO-Werte oder nicht archivierte Evidence blockieren Live.

## Philipp liest den Report

Philipp prueft `Status`, `RTO Sekunden`, `RPO Sekunden` und `Live-ready`. Nur ein
separat ausgefuehrter Test-DB-Restore mit akzeptierten RTO/RPO-Werten kann in
die private Live-Freigabe eingehen.
