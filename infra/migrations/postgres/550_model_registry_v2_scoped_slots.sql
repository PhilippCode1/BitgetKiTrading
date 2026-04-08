-- Scoped Champion/Challenger: pro Marktfamilie, Regime, Playbook, Router-Slot (zusaetzlich global).

ALTER TABLE app.model_registry_v2
    ADD COLUMN IF NOT EXISTS scope_type text,
    ADD COLUMN IF NOT EXISTS scope_key text;

UPDATE app.model_registry_v2
SET scope_type = 'global', scope_key = ''
WHERE scope_type IS NULL OR scope_key IS NULL;

ALTER TABLE app.model_registry_v2
    ALTER COLUMN scope_type SET DEFAULT 'global',
    ALTER COLUMN scope_key SET DEFAULT '';

ALTER TABLE app.model_registry_v2
    ALTER COLUMN scope_type SET NOT NULL,
    ALTER COLUMN scope_key SET NOT NULL;

ALTER TABLE app.model_registry_v2
    DROP CONSTRAINT IF EXISTS uq_model_registry_v2_model_role;

ALTER TABLE app.model_registry_v2
    ADD CONSTRAINT chk_model_registry_v2_scope_type CHECK (
        scope_type IN ('global', 'market_family', 'market_regime', 'playbook', 'router_slot')
    );

ALTER TABLE app.model_registry_v2
    ADD CONSTRAINT uq_model_registry_v2_scoped_slot UNIQUE (model_name, role, scope_type, scope_key);

CREATE INDEX IF NOT EXISTS idx_model_registry_v2_scope_lookup
    ON app.model_registry_v2 (model_name, role, scope_type, scope_key);

COMMENT ON COLUMN app.model_registry_v2.scope_type IS
    'global = bisheriges Verhalten; sonst Spezialisten-Slot';
COMMENT ON COLUMN app.model_registry_v2.scope_key IS
    'Leer bei global; sonst z. B. futures, trend, playbook_id, router_slot_id';

-- Champion-Historie: eine offene Zeile pro (model_name, scope_type, scope_key)
ALTER TABLE app.model_champion_history
    ADD COLUMN IF NOT EXISTS scope_type text,
    ADD COLUMN IF NOT EXISTS scope_key text;

UPDATE app.model_champion_history
SET scope_type = 'global', scope_key = ''
WHERE scope_type IS NULL OR scope_key IS NULL;

ALTER TABLE app.model_champion_history
    ALTER COLUMN scope_type SET DEFAULT 'global',
    ALTER COLUMN scope_key SET DEFAULT '';

ALTER TABLE app.model_champion_history
    ALTER COLUMN scope_type SET NOT NULL,
    ALTER COLUMN scope_key SET NOT NULL;

DROP INDEX IF EXISTS uq_model_champion_history_open_scoped;

CREATE UNIQUE INDEX uq_model_champion_history_open_scoped
    ON app.model_champion_history (model_name, scope_type, scope_key)
    WHERE ended_at IS NULL;

-- Stabiler Rollback-Punkt pro Scope
ALTER TABLE app.model_stable_champion_checkpoint
    ADD COLUMN IF NOT EXISTS scope_type text,
    ADD COLUMN IF NOT EXISTS scope_key text;

UPDATE app.model_stable_champion_checkpoint
SET scope_type = 'global', scope_key = ''
WHERE scope_type IS NULL OR scope_key IS NULL;

ALTER TABLE app.model_stable_champion_checkpoint
    ALTER COLUMN scope_type SET DEFAULT 'global',
    ALTER COLUMN scope_key SET DEFAULT '';

ALTER TABLE app.model_stable_champion_checkpoint
    ALTER COLUMN scope_type SET NOT NULL,
    ALTER COLUMN scope_key SET NOT NULL;

ALTER TABLE app.model_stable_champion_checkpoint
    DROP CONSTRAINT IF EXISTS model_stable_champion_checkpoint_pkey;

ALTER TABLE app.model_stable_champion_checkpoint
    ADD PRIMARY KEY (model_name, scope_type, scope_key);
