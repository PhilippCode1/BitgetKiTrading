/** @jest-environment node */

import { isRetryableGatewayGetStatus } from "@/lib/gateway-upstream-fetch";

describe("gateway-upstream-fetch helpers", () => {
  it("isRetryableGatewayGetStatus allows transient upstream codes", () => {
    expect(isRetryableGatewayGetStatus(502)).toBe(true);
    expect(isRetryableGatewayGetStatus(503)).toBe(true);
    expect(isRetryableGatewayGetStatus(504)).toBe(true);
    expect(isRetryableGatewayGetStatus(408)).toBe(true);
    expect(isRetryableGatewayGetStatus(429)).toBe(true);
    expect(isRetryableGatewayGetStatus(401)).toBe(false);
    expect(isRetryableGatewayGetStatus(404)).toBe(false);
  });
});
