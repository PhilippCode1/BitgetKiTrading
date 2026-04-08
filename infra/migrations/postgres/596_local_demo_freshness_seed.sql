-- Forward-only Platzhalter: Frueher Demo-INSERTs fuer Kerzen/News (siehe Handoff 05/08).
-- Demo-Daten liegen nur noch unter infra/migrations/postgres_demo/ und werden ausschliesslich
-- angewendet, wenn BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true und `python infra/migrate.py --demo-seeds`
-- (Compose-Migrate-Entrypoint nach Hauptlauf). Shadow/Production: Flag verboten (validate_env_profile).
-- Dateiname bleibt fuer bereits eingetragene app.schema_migrations Zeilen.

SELECT 1;
