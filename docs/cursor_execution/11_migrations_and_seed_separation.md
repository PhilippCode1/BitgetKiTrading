# 11 — Migrations- und Seed-Trennung (Pipeline vs. Demo vs. Fixture)

**Stand:** 2026-04-05  
**Bezug:** Handoff `05_DATENFLUSS_*`, `08_FEHLER_ALERTS_*` (irreführende Demo-Daten)

---

## 1. Ziel

| Pfad                              | Bedeutung                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Kanonische Schema-Migrationen** | Produktiv relevant: Tabellen, Indizes, Constraints, Drift der App-DB.                                        |
| **Demo-SQL (`postgres_demo`)**    | Nur Entwicklung/Demo: Platzhalter-Zeilen, wenn Tabellen leer — **nie** Shadow/Production.                    |
| **Runtime-Fixtures**              | `NEWS_FIXTURE_MODE`, `PAPER_CONTRACT_CONFIG_MODE=fixture`, `BITGET_DEMO_ENABLED` — ENV-gesteuert, nicht SQL. |

Die Oberfläche soll **nicht** still „Live“ vortäuschen: `GET /v1/live/state` liefert **`demo_data_notice`** (Banner im Terminal und Konsole-Marktchart).

---

## 2. Technischer Ablauf

### 2.1 Kanonischer Pfad

- Verzeichnis: `infra/migrations/postgres/*.sql`
- Runner: `python infra/migrate.py` (Standard `DATABASE_URL`)
- Tracking: `app.schema_migrations.filename`
- Fehler: **Transaktion pro Datei** — bei SQL-Fehler **Abbruch** mit Exit-Code 1 und Logzeile `[migrate] ERROR phase=execute …` (kein stiller Halbschatten).
- Readiness: Gateway `GET /ready` / `get_db_health()` prüft **fehlende Kern-Tabellen** und **pending** Dateien aus dem **Katalog nur unter `postgres/`** (ohne `postgres_demo`).

### 2.2 Demo-SQL (optional, nur mit Flag)

- Verzeichnis: `infra/migrations/postgres_demo/*.sql`  
  Aktuell: `910_demo_local_freshness_seed.sql`, `911_demo_local_ticker_drawings.sql`, `912_demo_local_learning_registry_seed.sql`
- Aktivierung: **`BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true`** (nur non-production).
- Runner: **`python infra/migrate.py --demo-seeds`** (zweite Phase).
- Compose: `infra/docker/migrate_entrypoint.sh` ruft nach Hauptmigration automatisch `--demo-seeds` auf.
- **Verbot:** `PRODUCTION=true` zusammen mit `BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true` → **Exit 1** mit klarer Meldung.
- Validierung: `tools/validate_env_profile.py` lehnt die Kombination für Profile **shadow/staging/production** ab.

### 2.3 Platzhalter-Dateien 596 / 597 / 603

Die Dateinamen bleiben in `postgres/` (**Forward-only**), enthalten aber nur **`SELECT 1`** und Verweis auf `postgres_demo`. Bereits angewendete Datenbanken behalten den Eintrag in `schema_migrations`; **neue** Installationen bekommen **keine** Demo-INSERTs mehr aus diesen Dateien.

---

## 3. Produktiv kritisch vs. nur Demo

| Kategorie            | Beispiele                                                                 | Shadow/Prod             |
| -------------------- | ------------------------------------------------------------------------- | ----------------------- |
| **Kritisch**         | `000`–`595`, `598`–`602`, `604`–`614`, … (Schema, Ops, Commercial, Gates) | **Immer** anwenden      |
| **No-Op / Historie** | `596_local_demo_*`, `597_*`, `603_*`                                      | Läuft mit, ohne Daten   |
| **Demo-SQL**         | `910`–`912` unter `postgres_demo/`                                        | **Nie** (Flag verboten) |

---

## 4. UI: `demo_data_notice`

Das Gateway setzt im Live-State:

- `show_banner` + `reasons[]` aus **ENV** (`NEWS_FIXTURE_MODE`, `BITGET_DEMO_ENABLED`) und **DB-Spuren** (z. B. `local_demo_seed`, `demo_local_seed`, Migration-Namen mit `local_demo` oder `NNN_demo_`).

Dashboard: `DemoDataNoticeBanner` (Terminal, Konsole-Marktchart), Texte unter `live.terminal.demoData*` in `de.json` / `en.json`.

---

## 5. Nachweise (ausgeführt im Repo, 2026-04-05)

### 5.1 Layout-Check (ohne DB)

```text
python tools/check_migration_demo_layout.py
```

Ausgabe (stdout):

```text
check_migration_demo_layout: OK (3 demo-sql, Platzhalter 596/597/603)
```

Exit-Code: **0**.

### 5.2 Migrate Demo-Gate (ohne erreichbare DB)

Ohne Flag (stdout enthält Skip):

```text
[migrate] demo-seeds skipped (BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true fuer lokale Demo-INSERTs)
```

Exit-Code: **0** (kein DB-Connect bei Skip).

Mit `PRODUCTION=true` und `BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true`: Exit **1**, stderr enthält **`verboten`** (siehe `tests/unit/infra/test_migrate_demo_seeds_gate.py`).

### 5.3 Pytest (Gate)

```text
pytest tests/unit/infra/test_migrate_demo_seeds_gate.py -q
```

Ergebnis: **3 passed** (gleiche Session).

### 5.4 Selfcheck

```text
python tools/production_selfcheck.py
```

Ergebnis: **Exit 0** — u. a. ruff/black/mypy, pytest Modul-Mate-Paket, `check_contracts`, `check_schema`, `validate_env_profile` auf `.env.local.example` (DB-Teil: SKIP ohne `DATABASE_URL`).

### 5.5 validate_env_profile (Shadow + verbotenes Flag)

Temporäre `.env` mit `PRODUCTION=true`, `BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true` und `--profile shadow`: Exit **1**, in der Problemliste u. a.:

```text
BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true ist fuer shadow/production/staging verboten
```

### 5.6 DB-Nachweis (lokal, wenn Postgres läuft)

```text
set DATABASE_URL=postgresql://...
python infra/migrate.py
python infra/migrate.py --demo-seeds
```

Dann z. B. `SELECT source FROM app.news_items WHERE source='local_demo_seed' LIMIT 1;` — nur nach Demo-Lauf mit Flag.

---

## 6. Geänderte Artefakte (Kurz)

- `infra/migrate.py`, `infra/docker/Dockerfile.migrate`, `infra/docker/migrate_entrypoint.sh`
- `infra/migrations/postgres_demo/*.sql`, No-Op `596`/`597`/`603`
- `scripts/bootstrap_stack.sh`, `bootstrap_stack.ps1`
- `services/api-gateway/.../db_live_queries.py`, `routes_live.py`
- `apps/dashboard`: `DemoDataNoticeBanner`, `LiveTerminalClient`, `ConsoleLiveMarketChartSection`, `types.ts`, `de.json`, `en.json`
- `tools/validate_env_profile.py`, `tools/check_migration_demo_layout.py`
- `.env.local.example`, `.env.shadow.example`
- Doku: `migrations.md`, `data_pipeline_overview.md`, `db-schema.md`, `model_registry_v2.md`, Handoff 05/08

---

## 7. Offene Punkte

- `[TECHNICAL_DEBT]` Alte Datenbanken können noch **physische** Demo-Zeilen aus der Zeit vor diesem Vertrag enthalten — Banner erkennt typische Marker; Cleanup manuell möglich.
- `[FUTURE]` Einrichtung `pnpm`-Script für `check_migration_demo_layout.py` in CI optional ergänzen.
