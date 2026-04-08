import { applyGatewayReadStatusHeaders } from "@/lib/gateway-read-response-headers";

describe("applyGatewayReadStatusHeaders", () => {
  it("setzt Header fuer degraded JSON", () => {
    const h = new Headers();
    applyGatewayReadStatusHeaders(
      h,
      JSON.stringify({
        status: "degraded",
        degradation_reason: "database_error",
      }),
      "application/json",
    );
    expect(h.get("X-Gateway-Read-Status")).toBe("degraded");
    expect(h.get("X-Gateway-Degradation-Reason")).toBe("database_error");
  });

  it("setzt Header fuer empty", () => {
    const h = new Headers();
    applyGatewayReadStatusHeaders(
      h,
      JSON.stringify({ status: "empty", degradation_reason: "no_rows" }),
      "application/json",
    );
    expect(h.get("X-Gateway-Read-Status")).toBe("empty");
  });

  it("ignoriert nicht-JSON Content-Type", () => {
    const h = new Headers();
    applyGatewayReadStatusHeaders(h, "{}", "text/plain");
    expect(h.get("X-Gateway-Read-Status")).toBeNull();
  });
});
