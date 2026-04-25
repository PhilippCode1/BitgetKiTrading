import {
  redactCustomerMeJson,
  redactIntegrationsJson,
  type CustomerMeRedacted,
  type CustomerIntegrationsRedacted,
} from "@/lib/customer-portal-summary";

describe("customer-portal-summary redaction", () => {
  it("parst customer/me in ein redigiertes Modell", () => {
    const raw = {
      schema_version: "tenant-customer-me-v1",
      tenant: { id_masked: "tnt_***123" },
      profile: { display_name: "Max" },
      plan: {
        plan_id: "starter",
        display_name: "Starter",
        transparency_note: "read-only",
      },
      tenant_state: { budget_cap_usd_month: 1000 },
      access: { portal: true, admin: false, non_boolean: "x" },
      telegram: {
        connected: true,
        console_telegram_required: false,
        migration_required: true,
      },
    };

    const out = redactCustomerMeJson(raw) as CustomerMeRedacted;
    expect(out).not.toBeNull();
    expect(out.tenantIdMasked).toBe("tnt_***123");
    expect(out.profile.displayName).toBe("Max");
    expect(out.plan.displayName).toBe("Starter");
    expect(out.accessMatrix).toEqual({ portal: true, admin: false });
    expect(out.telegram).toEqual({
      connected: true,
      consoleTelegramRequired: false,
      migrationRequired: true,
    });
  });

  it("filtert geheime Schluessel aus integrations.bitget_env", () => {
    const raw = {
      tenant_id_masked: "tnt_***123",
      integration: {
        broker_state: "connected",
        broker_hint_public: "configured",
        telegram_state: "connected",
        telegram_hint_public: "ok",
      },
      bitget_env: {
        env: "paper",
        hint_public_de: "Nur Status sichtbar",
        api_key: "should_not_leak",
        secret: "should_not_leak",
        tokenValue: "should_not_leak",
      },
    };

    const out = redactIntegrationsJson(raw) as CustomerIntegrationsRedacted;
    expect(out).not.toBeNull();
    expect(out.bitgetEnv).toEqual({
      env: "paper",
      hint_public_de: "Nur Status sichtbar",
    });
    expect(JSON.stringify(out)).not.toMatch(/should_not_leak/);
  });

  it("liefert null bei unvollstaendigem customer/me payload", () => {
    expect(redactCustomerMeJson({ schema_version: "v1" })).toBeNull();
  });
});
