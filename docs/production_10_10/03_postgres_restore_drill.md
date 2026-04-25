# Postgres-Restore-Drill (RTO/RPO-Nachweis)

Normativ eng mit `docs/recovery_runbook.md` und der Launch-Checkliste verzahnt. Das Werkzeug prüft **lokal oder gegen eine Test-/Staging-DSN**, ob `pg_dump` (Schema-Filter), `DROP` und `psql -f` funktionieren und ob eine Inhalts-Checksumme vor und nach dem Restore identisch ist. **Kein `PASS`**, wenn weder Verbindung noch Werkzeuge (oder `psycopg`) vorhanden sind.

## Werkzeuge

- `tools/dr_postgres_restore_drill.py` (Hauptimplementierung)
- `scripts/dr_postgres_restore_drill.py` (dünner Wrapper, gleiche Argumente)

## Voraussetzungen (Host)

- `psycopg` (Python) installiert, sonst erscheint in `tool_check` u. a. `python-psycopg`
- `pg_dump` und `psql` im `PATH` (macOS/Linux; unter Windows: Installations-`bin` in PATH, ggf. `psql.exe`)
- DSN: `--database-url` **oder** `--env-file` mit `DATABASE_URL` bzw. mit `--prefer-test-url` zuerst `TEST_DATABASE_URL`

## Staging: Schritt-für-Schritt (Operator)

1. Sichere **nur** eine Staging-/Clone-`DATABASE_URL` in Secret Manager/Shell, nicht in Commit/Logs. Keine produktive Haupt-DB destruktiv ansprechen, wenn eure Policy das verbietet — das Skript arbeitet in einem **eigenen Schema** `dr_restore_drill_*`, führt aber lokalen `DROP` nach Backup aus: nur gegen akzeptierte Umgebung ausführen.
2. Arbeitsverzeichnis: Repo-Root. Artefakt-Ordner wählen, z. B. `export DR_ART=reports/dr_staging_$(date +%Y%m%d)`.
3. Optional Hart-Gates: `--require-rto-sec <Sekunden>` (gemessene Restore-Phase) und `--require-rpo-sec` (RPO-Modell: ab Insert bis `pg_dump` fertig; siehe Markdownt-Bericht).
4. Befehl (Beispiel):
   - `python tools/dr_postgres_restore_drill.py --env-file /pfad/zur/staging.env --output-md $DR_ART/report.md --artifact-dir $DR_ART/artifacts --require-rto-sec 600 --require-rpo-sec 30`
5. **Exit-Code 0** nur bei `PASS` bzw. bei `--dry-run` in den dokumentierten OK-Pfaden (siehe Hilfe). `MISSING_TOOL` oder `MISSING_DATABASE` = kein `PASS` für Geld-Freigabe.
6. Bericht und `result.json` aus `--artifact-dir` in Release-Evidence / DMS ablegen. Im Bericht: `git_sha` (CI oder lokales `git` wenn vorhanden), Zeile **Time (UTC)**, DSN-sanitisiert, RTO/RPO, Gates.

## Dry-Run (ohne Schema-Mutation, ohne DSN)

Prüft nur, ob Werkzeuge auffindbar sind (bzw. mit DSN: Verbindung, ohne vollen Drill):

- `python tools/dr_postgres_restore_drill.py --dry-run --output-md /tmp/dr_dry.md --artifact-dir /tmp/dr_a`

Fehlende `pg_dump`/`psql` → `MISSING_TOOL` und Exit-Code 1, Bericht wird trotzdem geschrieben, damit Betrieb sieht, was fehlt.

## CI / lokale Qualität

- Unit-Tests: `python -m pytest tests/unit/tools/test_dr_postgres_restore_drill.py -q`
- Echter Restore-Lauf: nur mit laufendem Postgres und installierten Clients; andernfalls bewusst `MISSING_TOOL` / `BLOCKED_EXTERNAL`
