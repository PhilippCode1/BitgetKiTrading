-- Prompt 12: Vertragsvorlagen (versioniert), PDF-Revisionen (bytea, append-only), E-Sign-Webhook, Admin-Queue.

CREATE TABLE IF NOT EXISTS app.contract_template (
    template_key text NOT NULL,
    version int NOT NULL,
    title_de text NOT NULL,
    body_text text NOT NULL,
    content_sha256_hex text NOT NULL,
    effective_from date NOT NULL DEFAULT CURRENT_DATE,
    is_active boolean NOT NULL DEFAULT true,
    created_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (template_key, version),
    CONSTRAINT chk_contract_template_version CHECK (version >= 1),
    CONSTRAINT chk_contract_template_title_len CHECK (char_length(title_de) <= 240)
);

COMMENT ON TABLE app.contract_template IS
    'Versionierte Vertragsvorlagen; body_text ist PDF-Quelltext (Plain), keine Secrets.';

CREATE TABLE IF NOT EXISTS app.tenant_contract (
    contract_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    template_key text NOT NULL,
    template_version int NOT NULL,
    status text NOT NULL,
    provider_name text NOT NULL DEFAULT 'mock',
    provider_envelope_id text,
    signing_url_hint text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_tenant_contract_template FOREIGN KEY (template_key, template_version)
        REFERENCES app.contract_template (template_key, version),
    CONSTRAINT chk_tenant_contract_status CHECK (
        status IN (
            'awaiting_customer_sign',
            'awaiting_provider_sign',
            'signed_awaiting_admin',
            'admin_review_complete',
            'void'
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_contract_one_open
    ON app.tenant_contract (tenant_id)
    WHERE status IN (
        'awaiting_customer_sign',
        'awaiting_provider_sign',
        'signed_awaiting_admin'
    );

CREATE INDEX IF NOT EXISTS idx_tenant_contract_tenant_updated
    ON app.tenant_contract (tenant_id, updated_ts DESC);

COMMENT ON TABLE app.tenant_contract IS
    'Eine laufende oder abgeschlossene Vertragsinstanz je Tenant (max. eine offene).';

CREATE TABLE IF NOT EXISTS app.tenant_contract_document (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id uuid NOT NULL REFERENCES app.tenant_contract (contract_id) ON DELETE CASCADE,
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    document_kind text NOT NULL,
    sha256_hex text NOT NULL,
    byte_size bigint NOT NULL,
    pdf_bytes bytea NOT NULL,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_tenant_contract_document_kind CHECK (
        document_kind IN ('draft_pdf', 'signed_pdf')
    ),
    CONSTRAINT chk_tenant_contract_document_size CHECK (byte_size >= 0 AND byte_size <= 10485760)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_contract_document_sha
    ON app.tenant_contract_document (sha256_hex);

CREATE INDEX IF NOT EXISTS idx_tenant_contract_document_contract
    ON app.tenant_contract_document (contract_id, created_ts DESC);

COMMENT ON TABLE app.tenant_contract_document IS
    'Unveraenderliche PDF-Revisionen (draft/signed); keine Updates, nur INSERT.';

CREATE TABLE IF NOT EXISTS app.contract_review_queue (
    queue_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id uuid NOT NULL REFERENCES app.tenant_contract (contract_id) ON DELETE CASCADE,
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    queue_status text NOT NULL,
    admin_notes_internal text,
    customer_message_public text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_contract_review_queue_status CHECK (
        queue_status IN (
            'pending_review',
            'needs_customer_info',
            'approved_contract',
            'rejected',
            'closed'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_contract_review_queue_status
    ON app.contract_review_queue (queue_status, created_ts DESC);

COMMENT ON TABLE app.contract_review_queue IS
    'Admin-Warteschlange: Pruefung, Rueckfrage, Freigabe-Hinweis fuer Kunden.';

INSERT INTO app.contract_template (
    template_key,
    version,
    title_de,
    body_text,
    content_sha256_hex,
    is_active
)
VALUES (
    'modul_mate_standard_v1',
    1,
    'Kundenvereinbarung Modul Mate (Standard v1)',
    'MODUL MATE GMBH - KUNDENVEREINBARUNG v1' || chr(10) || chr(10) ||
    '1. Gegenstand: Plattformnutzung.' || chr(10) ||
    '2. Live-Handel nur nach Admin-Freigabe.' || chr(10) ||
    '3. Risikohinweis Handel.' || chr(10) ||
    '4. Datenschutz nach geltendem Recht.' || chr(10) ||
    '5. Schlussbestimmungen DE.' || chr(10),
    'c10009f3e28ece91514d33773fd4d09c28d8c8c35008299fb5fcb2c5ff593010',
    true
)
ON CONFLICT (template_key, version) DO NOTHING;
