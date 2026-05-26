-- P80: Ergaenzung des Instrumentenkatalogs fuer Hybrid-Bot-Trading Eligibility & Hebelgrenzen.
-- Sowie Erweiterung des Audit-Logs fuer reale Marktfills (live.fills).

-- 1. Erweiterung des Instrumentenkatalogs (app.instrument_catalog_entries)
ALTER TABLE app.instrument_catalog_entries
    ADD COLUMN IF NOT EXISTS bot_trading_supported boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS assigned_leverage integer NULL,
    ADD COLUMN IF NOT EXISTS execution_mode text NULL CHECK (execution_mode IN ('BOT_GRID', 'BOT_DCA', 'STANDARD_FUTURES'));

-- Teilindex fuer bot-faehige Assets fuer ultraschnelle Lookups
CREATE INDEX IF NOT EXISTS idx_instrument_catalog_entries_bot_eligible 
    ON app.instrument_catalog_entries (canonical_instrument_id) 
    WHERE bot_trading_supported = true AND trading_enabled = true;

-- Kommentare fuer den Instrumentenkatalog
COMMENT ON COLUMN app.instrument_catalog_entries.bot_trading_supported IS
    'Flag, ob das Asset nativ ueber die Bitget-Plan/Grid-API betrieben werden kann.';
COMMENT ON COLUMN app.instrument_catalog_entries.assigned_leverage IS
    'Der von der KI zuletzt fuer dieses Instrument berechnete oder zugewiesene dynamische Hebel.';
COMMENT ON COLUMN app.instrument_catalog_entries.execution_mode IS
    'Der aktuelle oder standardmaessig vorgesehene Betriebsmodus fuer dieses Instrument (BOT_GRID, BOT_DCA, STANDARD_FUTURES).';


-- 2. Erweiterung des Audit-Logs fuer reale Marktfills (live.fills)
ALTER TABLE live.fills
    ADD COLUMN IF NOT EXISTS execution_mode text NULL CHECK (execution_mode IN ('BOT_GRID', 'BOT_DCA', 'STANDARD_FUTURES')),
    ADD COLUMN IF NOT EXISTS applied_leverage integer NULL,
    ADD COLUMN IF NOT EXISTS bot_strategy_id text NULL;

-- Indizes fuer das Fills Audit-Log zur Optimierung nachgelagerter Kontrollen und Dashboards
CREATE INDEX IF NOT EXISTS idx_live_fills_bot_strategy_id 
    ON live.fills (bot_strategy_id) 
    WHERE bot_strategy_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_live_fills_execution_mode 
    ON live.fills (execution_mode);

-- Kommentare fuer das Fills Audit-Log
COMMENT ON COLUMN live.fills.execution_mode IS
    'Der gewaehlte Ausfuehrungsmodus der Order (BOT_GRID, BOT_DCA, STANDARD_FUTURES).';
COMMENT ON COLUMN live.fills.applied_leverage IS
    'Der angewandte Hebel zum Zeitpunkt der Order-Ausfuehrung.';
COMMENT ON COLUMN live.fills.bot_strategy_id IS
    'Die offizielle Bitget-Bot-Strategie-ID, falls dieser Fill von einem nativer Bot generiert wurde.';
