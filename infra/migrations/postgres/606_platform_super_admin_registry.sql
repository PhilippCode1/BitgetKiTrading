-- Prompt 10: Anker fuer alleinigen Super-Admin (Anzeige/Audit); technische JWT-Pruefung: GATEWAY_SUPER_ADMIN_SUBJECT.

CREATE TABLE IF NOT EXISTS app.platform_super_admin_registry (
    singleton_key text PRIMARY KEY DEFAULT 'singleton' CHECK (char_length(singleton_key) <= 32),
    canonical_display_name text NOT NULL,
    notes text NOT NULL DEFAULT '',
    seeded_ts timestamptz NOT NULL DEFAULT now()
);

INSERT INTO app.platform_super_admin_registry (singleton_key, canonical_display_name, notes)
VALUES (
    'singleton',
    'Philipp Crljic',
    'Alleiniger Voll-Admin [FEST]. JWT sub muss GATEWAY_SUPER_ADMIN_SUBJECT entsprechen; portal_roles super_admin sonst wirkungslos.'
)
ON CONFLICT (singleton_key) DO NOTHING;

COMMENT ON TABLE app.platform_super_admin_registry IS
    'Produktanker Super-Admin (Modul Mate); keine Credentials. Subject-Bindung nur per ENV am Gateway.';

-- Mandantenbezogene Identitaets-Hinweise (keine Passwoerter/Secrets; Erweiterung fuer IdP/OTP).
CREATE TABLE IF NOT EXISTS app.portal_identity_security (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    email_verified_at timestamptz,
    mfa_totp_enabled boolean NOT NULL DEFAULT false,
    password_login_configured boolean NOT NULL DEFAULT false,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE app.portal_identity_security IS
    'Konto-Sicherheitsflags je Tenant; Session/Reset/MFA-Flows werden angebunden, keine Klartext-Passwoerter.';

INSERT INTO app.portal_identity_security (tenant_id)
SELECT tenant_id FROM app.tenant_commercial_state
ON CONFLICT (tenant_id) DO NOTHING;
