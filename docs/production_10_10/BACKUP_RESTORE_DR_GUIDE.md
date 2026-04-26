# Backup Restore DR Guide

## 1) Welche Backups gebraucht werden

- Postgres-Backups mit Label und SHA256.
- Backup-Speicher muss verschluesselt sein (sonst `external_required`).
- Retention und Aufbewahrungsfenster muessen dokumentiert sein.

## 2) Welche Umgebung fuer Restore-Test

Nur Staging-/Clone-Umgebung. Kein Restore-Drill gegen produktive Live-DB.

## 3) Wie Restore-Test ausgefuehrt wird

```bash
python scripts/dr_postgres_restore_test.py --dry-run --output-md reports/postgres_restore_drill.md --output-json reports/postgres_restore_drill.json
python tools/dr_postgres_restore_drill.py --help
```

Echter Restore-Nachweis wird extern als JSON-Evidence gegen
`docs/production_10_10/postgres_restore_evidence.template.json` geprueft.

## 4) Was RTO bedeutet

RTO = maximal tolerierte Wiederherstellungszeit bis zum kontrollierten, sicheren Betriebszustand.

## 5) Was RPO bedeutet

RPO = maximal tolerierter Datenverlustzeitraum zwischen letztem gueltigen Backup und Restore-Punkt.

## 6) Welche Reports entstehen

- `reports/backup_dr_evidence.md`
- `reports/backup_dr_evidence.json`
- `reports/postgres_restore_drill.md`
- `reports/postgres_restore_drill.json`
- `reports/disaster_recovery_drill.md`
- `reports/disaster_recovery_drill.json`

## 7) Warum Backup ohne Restore-Test nicht reicht

Ohne Restore-Beweis bleibt unklar, ob Backup lesbar, konsistent und in Budget (RTO/RPO) wiederherstellbar ist.

## 8) Wie nach Restore Reconcile laeuft

Nach Recovery bleiben Opening-Orders blockiert, bis Reconcile clean ist, Exchange-Truth vorliegt und Operator-Review dokumentiert wurde.

## 9) Wann `backup_restore` verified werden darf

Nur mit echtem Staging-/Clone-Restore, PASS-Status, RTO/RPO, Git-SHA, Schema-/Migration-Check, Audit-Check und Owner-Review.

## 10) Wann `disaster_recovery` verified werden darf

Nur mit echtem DR-Drill ueber DB/Redis/Service-Restarts plus Reconcile-, Alert- und Safety-Latch-Nachweis inklusive Owner-Review.

## 11) Warum Live ohne Restore-/DR-Drill NO_GO bleibt

Ohne echte Recovery-Evidence ist nicht bewiesen, dass das System nach Fehlern fail-closed bleibt und keine unkontrollierten Live-Aktionen ausloest.
