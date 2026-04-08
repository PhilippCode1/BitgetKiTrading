-- Prompt 27: Replay-Session-Manifest fuer Reproduzierbarkeit / Audit

ALTER TABLE learn.replay_sessions
    ADD COLUMN IF NOT EXISTS manifest_json jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN learn.replay_sessions.manifest_json IS
    'Determinismus- und Schema-Metadaten (Modellcontract, Policy-Caps, Seeds); Prompt 27.';
