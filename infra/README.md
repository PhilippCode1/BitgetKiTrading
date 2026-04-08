# Infra: Postgres-Migrationen

## Ablauf

- **Runner:** `infra/migrate.py` (auch Docker-Image `migrate`, Alert-Engine-Bootstrap).
- **Verzeichnis:** `infra/migrations/postgres/*.sql` — ausschließlich **UTF-8** (optional BOM), **keine** UTF-16- oder Binärdateien.
- **Reihenfolge:** lexikographisch nach **Dateiname** (`sorted(..., key=name)`). Präfixe numerisch halten (`010_...`, `020_...`), damit die Sortierung der intendierten Reihenfolge entspricht. **Keine doppelten Präfixe** (z. B. zwei `550_...`), um Verwirrung und Merge-Konflikte zu vermeiden.
- **Journal:** Tabelle `app.schema_migrations(filename text primary key, ...)`. Bereits eingetragene Dateien werden übersprungen (`skip reason=already_applied`).
- **Parallelität:** Standardmäßig `pg_advisory_lock`, damit nicht zwei Migratoren gleichzeitig laufen. Notfall: `python infra/migrate.py --no-advisory-lock`.

## Regeln für neue Migrationen

1. **Idempotent formulieren:** `CREATE … IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, wo Postgres es hergibt.
2. **Ein Dateiname = eine logische Version** — Datei nach Anwendung nicht mehr ändern; Korrekturen als neue Datei mit höherem Präfix.
3. **Reservierte Wörter:** Spalten/Aliase, die mit SQL-Schlüsselwörtern kollidieren (`window`, `user`, …), immer **doppelt quoten** (`"window"`).
4. **Encoding:** Nur **UTF-8** speichern (IDE „UTF-8“ / „UTF-8 with BOM“ ist ok). Keine Windows-1252-/Latin-1-Sonderzeichen ohne UTF-8-Bytefolge.
5. **Keine leeren Dateien** — leere oder nur-Whitespace-SQL wird abgelehnt.
6. **Tests:** Frische DB: erster Lauf `applied`, zweiter Lauf nur `skip`, keine Duplicate- oder Syntaxfehler.

## CLI

```bash
export DATABASE_URL="postgresql://USER:PASS@HOST:5432/DBNAME"
python infra/migrate.py
```

Optional:

```bash
python infra/migrate.py --migrations-dir /pfad/zu/sql
python infra/migrate.py --no-advisory-lock
```

## Markt-Stream (separat)

Unter `services/market-stream/migrations/` liegen zusätzliche TSDB-Skripte; sie werden **nicht** von `infra/migrate.py` ausgeführt (eigenes Deployment/Tooling).
