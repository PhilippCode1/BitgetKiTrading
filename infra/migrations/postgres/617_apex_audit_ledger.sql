-- Apex Predator Audit Ledger: append-only Entscheidungskette (War-Room / Konsens).
-- Integritaet: chain_hash = SHA256(prev_chain_hash || canonical_payload_utf8); Ed25519-Signatur ueber chain_hash.

CREATE TABLE IF NOT EXISTS app.apex_audit_ledger_entries (
    id bigserial PRIMARY KEY,
    decision_id uuid NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    prev_chain_hash bytea NOT NULL CHECK (octet_length(prev_chain_hash) = 32),
    canonical_payload_text text NOT NULL,
    chain_hash bytea NOT NULL CHECK (octet_length(chain_hash) = 32),
    signature bytea NOT NULL CHECK (octet_length(signature) = 64),
    signing_public_key bytea NOT NULL CHECK (octet_length(signing_public_key) = 32),
    war_room_version text,
    consensus_status text NOT NULL,
    final_signal_action text NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_apex_audit_ledger_created
    ON app.apex_audit_ledger_entries (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_apex_audit_ledger_consensus
    ON app.apex_audit_ledger_entries (consensus_status, final_signal_action);

COMMENT ON TABLE app.apex_audit_ledger_entries IS
    'INSERT-only Audit-Ledger; Updates/Deletes per Trigger verboten. '
    'Produktion: DB-Role nur INSERT+SELECT auf dieser Tabelle (kein UPDATE/DELETE).';

-- Append-only: auch Superuser-UPDATEs werden abgewiesen (Vorsicht: Migrationen aendern Tabelle nur ueber DROP/CREATE).
CREATE OR REPLACE FUNCTION app.apex_audit_ledger_reject_mutate()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'apex_audit_ledger append-only: UPDATE/DELETE forbidden (id=%)', OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_apex_audit_ledger_no_update ON app.apex_audit_ledger_entries;
CREATE TRIGGER tr_apex_audit_ledger_no_update
    BEFORE UPDATE ON app.apex_audit_ledger_entries
    FOR EACH ROW EXECUTE PROCEDURE app.apex_audit_ledger_reject_mutate();

DROP TRIGGER IF EXISTS tr_apex_audit_ledger_no_delete ON app.apex_audit_ledger_entries;
CREATE TRIGGER tr_apex_audit_ledger_no_delete
    BEFORE DELETE ON app.apex_audit_ledger_entries
    FOR EACH ROW EXECUTE PROCEDURE app.apex_audit_ledger_reject_mutate();
