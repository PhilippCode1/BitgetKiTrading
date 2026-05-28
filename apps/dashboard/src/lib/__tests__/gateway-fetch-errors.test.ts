import { getGatewayFetchErrorInfo } from "@/lib/gateway-fetch-errors";

describe("gateway-fetch-errors", () => {
  it("getGatewayFetchErrorInfo liefert kind + technische Zeile", () => {
    const r = new Error("GET /v1/x: HTTP 502");
    const i = getGatewayFetchErrorInfo(r);
    expect(i.kind).toBe("bad_gateway");
    expect(i.technical).toContain("HTTP 502");
  });

  it("klassifiziert Timeout-Strings", () => {
    const i = getGatewayFetchErrorInfo("request timeout");
    expect(i.kind).toBe("timeout");
    expect(i.technical).toBe("request timeout");
  });
});
