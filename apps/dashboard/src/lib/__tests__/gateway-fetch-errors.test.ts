import { gatewayFetchErrorMessage } from "@/lib/gateway-fetch-errors";

describe("gateway-fetch-errors", () => {
  it("gatewayFetchErrorMessage", () => {
    expect(gatewayFetchErrorMessage(new Error("x"))).toBe("x");
    expect(gatewayFetchErrorMessage("timeout")).toBe("timeout");
  });
});
