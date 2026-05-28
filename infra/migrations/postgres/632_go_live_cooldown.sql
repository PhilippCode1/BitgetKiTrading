-- Go-Live Cooldown: nach Self-Service-Aktivierung zunaechst Shadow-Phase,
-- bevor assert_execution_allowed LIVE-Exchange-Orders zulaesst.

ALTER TABLE app.tenant_modul_mate_gates
    ADD COLUMN IF NOT EXISTS live_go_live_at timestamptz NULL;

COMMENT ON COLUMN app.tenant_modul_mate_gates.live_go_live_at IS
    'Zeitpunkt der letzten Go-Live-Aktivierung; LIVE-Orders erst nach GO_LIVE_COOLDOWN_SEC.';
