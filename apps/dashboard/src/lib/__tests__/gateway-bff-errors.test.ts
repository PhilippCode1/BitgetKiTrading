import {
  DashboardBffErrorCode,
  jsonDashboardBffError,
} from "@/lib/gateway-bff-errors";

describe("jsonDashboardBffError", () => {
  it("liefert code und layer fuer Clients", async () => {
    const res = jsonDashboardBffError(
      503,
      DashboardBffErrorCode.DASHBOARD_GATEWAY_AUTH_MISSING,
      "Test detail",
    );
    expect(res.status).toBe(503);
    const j = (await res.json()) as {
      detail: string;
      code: string;
      layer: string;
    };
    expect(j.code).toBe("DASHBOARD_GATEWAY_AUTH_MISSING");
    expect(j.layer).toBe("dashboard-bff");
    expect(j.detail).toContain("Test detail");
  });
});
