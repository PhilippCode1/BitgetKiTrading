import { getGatewayFetchErrorInfo, gatewayFetchErrorMessage } from "@/lib/gateway-fetch-errors";

describe("gateway-fetch-errors", () => {
  it("getGatewayFetchErrorInfo liefert kind + technische Zeile", () => {
    const r = new Error("GET /v1/x: HTTP 502");
    const i = getGatewayFetchErrorInfo(r);
    expect(i.kind).toBe("bad_gateway");
    expect(i.technical).toContain("HTTP 502");
  });

  it("gatewayFetchErrorMessage (deprecated) liefert technische Zeile", () => {
    expect(gatewayFetchErrorMessage(new Error("x"))).toBe("x");
    expect(gatewayFetchErrorMessage("timeout")).toBe("timeout");
  });
});
