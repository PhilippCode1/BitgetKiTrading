-- Prompt 08: monitor-engine schreibt zusaetzliche check_type-Werte (Live-Broker, Online-Drift).
-- Altes CHECK erlaubte nur health/ready/metrics/latency -> CheckViolation bei reconcile etc.

DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT c.conname
    FROM pg_constraint c
    JOIN pg_class rel ON rel.oid = c.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'ops'
      AND rel.relname = 'service_checks'
      AND c.contype = 'c'
      AND pg_get_constraintdef(c.oid) ILIKE '%check_type%'
  LOOP
    EXECUTE format('ALTER TABLE ops.service_checks DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;

ALTER TABLE ops.service_checks
  ADD CONSTRAINT service_checks_check_type_allowed CHECK (
    check_type IN (
      'health',
      'ready',
      'metrics',
      'latency',
      'reconcile',
      'kill_switch',
      'audit',
      'shadow_live_divergence',
      'safety_latch',
      'ops_snapshot',
      'learn_online_drift_state'
    )
  );

COMMENT ON CONSTRAINT service_checks_check_type_allowed ON ops.service_checks IS
  'Kanonische check_type-Werte fuer HTTP-Probes, Live-Broker-Ops und Online-Drift (monitor-engine).';
