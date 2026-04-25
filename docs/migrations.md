# Migrations

## Quelle der Wahrheit

Ab Prompt 8 liegen die kanonischen Postgres-Migrationen in:

```text
infra/migrations/postgres/
```

Der Runner dazu ist:

```bash
python infra/migrate.py
```

## Reihenfolge und Naming

Konvention:

- `000_...sql`: Bootstrap / Schema-Grundlagen
- `010_...sql`, `020_...sql`, `030_...sql`: fachlich getrennte Schritte
- Dateinamen werden lexikografisch sortiert und genau in dieser Reihenfolge
  ausgefuehrt

Gleiche Nummer, mehrere Dateien (z. B. `410_*.sql`): die Reihenfolge ist
**zuerst numerisches Praefix, dann vollstaendiger Dateiname** (wie `infra/migrate.py`).
Neue Migrationen sollten trotzdem moeglichst **eindeutige Praefixe** nutzen, um
Verwechslungen zu vermeiden.

Wichtig:

- Migrationen muessen idempotent sein
- neue Migrationen duerfen bestehende Dateien nicht umschreiben
- write-forward only: neue Korrekturen kommen als neue Datei dazu

## Demo-SQL (nur lokal)

Optionaler zweiter Lauf: **`infra/migrations/postgres_demo/*.sql`** — dieselbe Tabelle `app.schema_migrations`,
eindeutige Dateinamen (z. B. `910_demo_...`). Aktivierung nur mit **`BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true`**;
`python infra/migrate.py --demo-seeds` (Compose-Image: Entrypoint nach Hauptmigration). In Shadow/Production
verboten (`validate_env_profile`). Die frueheren Dateinamen `596`/`597`/`603` unter `postgres/` sind **No-Op-Platzhalter** (forward-only, Demo-SQL nur im separaten Lauf).

## Tracking

Ausgefuehrte Migrationen werden in `app.schema_migrations` protokolliert:

- `filename`
- `applied_ts`

Ein zweiter Lauf von `python infra/migrate.py` darf nicht crashen und sollte nur
noch `skip` bzw. `no pending migrations` ausgeben.

## Lokaler Ablauf

```bash
docker compose up -d --build
python infra/migrate.py
python infra/migrate.py
curl -s http://localhost:8000/db/health
curl -s http://localhost:8000/db/schema
```

## Neue Migration hinzufuegen

1. Neue Datei in `infra/migrations/postgres/` anlegen.
2. Naechste freie Nummer waehlen, z. B. `040_add_feature_flags.sql`.
3. Nur additive oder klar migrationssichere Aenderungen schreiben.
4. `IF NOT EXISTS` bzw. additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
   bevorzugen.
5. Runner lokal zweimal starten und pruefen, dass der zweite Lauf no-op bleibt.

## Rollback-Strategie

Es gibt bewusst keine automatischen Down-Migrations.

Stattdessen gilt:

- write forward migrations
- bei Fehlern: neue Korrektur-Migration anlegen
- keine stillen manuellen DB-Eingriffe ausserhalb eines klar dokumentierten
  Incidents

## Produktionsnahe Deployments

Vor dem Ausrollen neuer Migrationen:

1. **Backup**: logischer Dump (`pg_dump`) oder Snapshot des Volume/der Instanz, sodass ein
   Wiederherstellungspunkt vor `python infra/migrate.py` existiert.
2. **Reihenfolge**: zuerst Datenbank migrieren, dann Dienste mit dem neuen Schema starten
   (Live-Broker prueft `schema_ready()` und benoetigt u. a. Tabellen aus `430_*`).
3. **Rollback**: kein automatisches Down-Skript; bei Fehlern Restore aus Backup oder
   eine nachfolgende Forward-Migration, die den Zustand korrigiert.

## Inventar (Kurzueberblick Domains)

| Bereich                            | Typische Migrationen (Auszug)                                                                                                                                                    |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Signals / Features                 | `070_signals_v1`, `080_signal_explanations`, `040_features`                                                                                                                      |
| News                               | `090_news_items`, `100_news_scoring`                                                                                                                                             |
| Paper                              | `110_paper_broker_core`, `120_paper_broker_stop_tp`                                                                                                                              |
| Learning / Strategie               | `140_learning_feedback`, `150_strategy_registry`, `160_learning_engine_v1`, `300_model_contracts` … `370_*`                                                                      |
| Monitoring / Ops                   | `230_alert_engine`, `240_ops_monitoring`                                                                                                                                         |
| Live-Broker                        | `250_live_broker` … `300_live_broker_exit_plans`, `430_live_audit_reconcile_risk_shadow`                                                                                         |
| Gateway / Replay / Drift / Modelle | `390_model_registry_v2`, `400_online_drift_state`, `410_replay_session_manifest`, `420_gateway_request_audit`, `550_model_registry_v2_scoped_slots` (scoped Champion/Challenger) |

**430** (`430_live_audit_reconcile_risk_shadow.sql`): `live.reconcile_runs` mit Verknuepfung zu
`reconcile_snapshots` und `exchange_snapshots` (FK), normalisierte Zeilen
`live.execution_risk_snapshots` und `live.shadow_live_assessments`, `fills.ingest_source`,
FK `order_actions` → `orders`, zusaetzliche Indizes fuer Signal-Lineage und Shadow-Gate-Forensik.
