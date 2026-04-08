-- Hebel-relevante Unsicherheit (Execution/Daten-Anteil) fuer Audit und Live-Bundle aus DB.

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS uncertainty_effective_for_leverage_0_1 numeric;
