-- Prompt 27: Reconcile: lokaler Spiegel offener Bitget-Positionen (keine stillen Zombies)
CREATE TABLE IF NOT EXISTS live.positions (
    position_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inst_id text NOT NULL,
    product_type text NOT NULL DEFAULT '',
    hold_side text NOT NULL CHECK (hold_side IN ('long', 'short')),
    size_base numeric NOT NULL DEFAULT 0,
    entry_price numeric,
    margin numeric,
    notional_value numeric,
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source text NOT NULL DEFAULT 'exchange' CHECK (source IN ('exchange', 'reconcile_shadow_sync', 'manual')),
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_live_positions_key
    ON live.positions (inst_id, product_type, hold_side);

CREATE INDEX IF NOT EXISTS idx_live_positions_updated
    ON live.positions (updated_ts DESC);

COMMENT ON TABLE live.positions IS
    'Live-Broker: gespiegelter Positionsstand fuer Drift-Erkennung (Exchange vs. DB); '
    'Reconcile kann Zeilen aus GET /v1/.../position nachziehen.';
