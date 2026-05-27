import {
  mapOidcProfileToPortalClaims,
  normalizePortalTenantId,
} from "@/lib/auth/portal-auth-adapter";

describe("portal-auth-adapter", () => {
  it("normalisiert gueltige Tenant-IDs", () => {
    expect(normalizePortalTenantId(" tenant_demo_123 ")).toBe("tenant_demo_123");
    expect(normalizePortalTenantId("bad id")).toBe("");
  });

  it("mappt OIDC-Kundenprofil auf Portal-JWT-Claims", () => {
    const prev = process.env.OIDC_DEFAULT_TENANT_ID;
    process.env.OIDC_DEFAULT_TENANT_ID = "tenant_demo_123";
    const claims = mapOidcProfileToPortalClaims({
      sub: "auth0|user1",
      email: "user@example.com",
      email_verified: true,
    });
    process.env.OIDC_DEFAULT_TENANT_ID = prev;
    expect(claims?.tenant_id).toBe("tenant_demo_123");
    expect(claims?.portal_roles).toContain("customer");
  });
});
