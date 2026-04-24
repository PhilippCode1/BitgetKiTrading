-- Prompt 67: Strategy Registry — version immutability, configuration_hash, live_champion.
-- (Aufgabe nannte einst "Migration 390"; 390 ist belegt durch model_registry_v2.)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE learn.strategy_versions
  ADD COLUMN IF NOT EXISTS configuration_hash text;

UPDATE learn.strategy_versions
SET configuration_hash = encode(
  digest(
    convert_to(
      (
        jsonb_build_object(
          'definition', COALESCE(definition_json, '{}'::jsonb),
          'parameters', COALESCE(parameters_json, '{}'::jsonb),
          'risk_profile', COALESCE(risk_profile_json, '{}'::jsonb)
        )
      )::text,
      'UTF8'
    ),
    'sha256'
  ),
  'hex'
)
WHERE configuration_hash IS NULL OR btrim(configuration_hash) = '';

ALTER TABLE learn.strategy_versions
  ALTER COLUMN configuration_hash SET NOT NULL;

ALTER TABLE learn.strategy_status
  ADD COLUMN IF NOT EXISTS live_champion_version_id uuid
    REFERENCES learn.strategy_versions (strategy_version_id) ON DELETE SET NULL;

DO $$
DECLARE
  cname text;
BEGIN
  SELECT c.conname INTO cname
  FROM pg_constraint c
  JOIN pg_class t ON c.conrelid = t.oid
  JOIN pg_namespace n ON t.relnamespace = n.oid
  WHERE n.nspname = 'learn'
    AND t.relname = 'strategy_status'
    AND c.contype = 'c'
  LIMIT 1;
  IF cname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE learn.strategy_status DROP CONSTRAINT %I', cname);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'learn_strategy_status_current_status_check'
  ) THEN
    ALTER TABLE learn.strategy_status
      ADD CONSTRAINT learn_strategy_status_current_status_check
      CHECK (
        current_status IN (
          'promoted',
          'candidate',
          'shadow',
          'retired',
          'live_champion'
        )
      );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'learn_strategy_status_champion_version_required'
  ) THEN
    ALTER TABLE learn.strategy_status
      ADD CONSTRAINT learn_strategy_status_champion_version_required
      CHECK (
        current_status <> 'live_champion' OR live_champion_version_id IS NOT NULL
      );
  END IF;
END $$;
