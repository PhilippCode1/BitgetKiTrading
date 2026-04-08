import {
  commerceAdminMutationAllowed,
  genericGatewayBffAllowsPostPath,
} from "@/lib/dashboard-bff-allowlists";

describe("genericGatewayBffAllowsPostPath", () => {
  it("erlaubt Vertrags-Root und Unterpfade", () => {
    expect(
      genericGatewayBffAllowsPostPath("/v1/commerce/customer/contracts"),
    ).toBe(true);
    expect(
      genericGatewayBffAllowsPostPath("/v1/commerce/customer/contracts/foo"),
    ).toBe(true);
  });

  it("verbietet Praefix-Tricks und andere Pfade", () => {
    expect(
      genericGatewayBffAllowsPostPath("/v1/commerce/customer/contractsX"),
    ).toBe(false);
    expect(
      genericGatewayBffAllowsPostPath("/v1/commerce/customer/contract"),
    ).toBe(false);
    expect(genericGatewayBffAllowsPostPath("/v1/admin/rules")).toBe(false);
  });
});

describe("commerceAdminMutationAllowed", () => {
  it("erlaubt nur die dokumentierten POST-Pfade", () => {
    expect(
      commerceAdminMutationAllowed(
        "POST",
        "/v1/commerce/admin/customer/lifecycle/transition",
      ),
    ).toBe(true);
    expect(
      commerceAdminMutationAllowed(
        "post",
        "/v1/commerce/admin/customer/wallet/adjust",
      ),
    ).toBe(true);
    expect(
      commerceAdminMutationAllowed(
        "POST",
        "/v1/commerce/admin/customer/lifecycle/set-email-verified",
      ),
    ).toBe(true);
    expect(
      commerceAdminMutationAllowed(
        "POST",
        "/v1/commerce/admin/customer/lifecycle/other",
      ),
    ).toBe(false);
  });

  it("erlaubt Dunning-PATCH nach Tenant-Slug", () => {
    expect(
      commerceAdminMutationAllowed(
        "PATCH",
        "/v1/commerce/admin/billing/tenant/acme/dunning",
      ),
    ).toBe(true);
    expect(
      commerceAdminMutationAllowed(
        "PATCH",
        "/v1/commerce/admin/billing/tenant//dunning",
      ),
    ).toBe(false);
  });

  it("verbietet andere Methoden", () => {
    expect(
      commerceAdminMutationAllowed(
        "DELETE",
        "/v1/commerce/admin/customer/wallet/adjust",
      ),
    ).toBe(false);
  });
});
