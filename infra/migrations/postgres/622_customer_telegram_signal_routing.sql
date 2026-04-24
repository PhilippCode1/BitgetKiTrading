-- Prompt 44: Zusaetzliche Filter fuer Strategie-/Signal-Telegram (HWM-Nebenfaden: Transparenz).
-- Erweitert 613: High-Leverage- und Signaltyp-Präferenzen, Plan-Familie siehe entitlements_json.

ALTER TABLE app.customer_telegram_notify_prefs
    ADD COLUMN IF NOT EXISTS notify_signal_high_leverage BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS signal_type_prefs_json JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN app.customer_telegram_notify_prefs.notify_signal_high_leverage IS
    'Wenn Falsch: Telegram bei Trades/Signalen oberhalb high_leverage_threshold (Gateway-Default) unterdruecken.';

COMMENT ON COLUMN app.customer_telegram_notify_prefs.signal_type_prefs_json IS
    'Pro Signaltyp (e.g. TREND_CONTINUATION) true/false. Fehlender Key = Voreinstellung wahr.';
