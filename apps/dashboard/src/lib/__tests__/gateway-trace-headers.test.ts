/** @jest-environment node */

import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";

describe("applyGatewayTraceHeaders", () => {
  it("generates UUIDs when nothing present", () => {
    const h = new Headers();
    applyGatewayTraceHeaders(h, null);
    const rid = h.get("X-Request-ID");
    const cid = h.get("X-Correlation-ID");
    expect(rid).toBeTruthy();
    expect(cid).toBe(rid);
    expect(rid!.length).toBeGreaterThan(20);
  });

  it("reuses incoming lowercase trace headers", () => {
    const src = new Headers();
    src.set("x-request-id", "rid-in");
    src.set("x-correlation-id", "corr-in");
    const h = new Headers();
    applyGatewayTraceHeaders(h, src);
    expect(h.get("X-Request-ID")).toBe("rid-in");
    expect(h.get("X-Correlation-ID")).toBe("corr-in");
  });

  it("does not override explicit outbound headers", () => {
    const src = new Headers();
    src.set("x-request-id", "from-client");
    const h = new Headers();
    h.set("X-Request-ID", "bff-fixed");
    applyGatewayTraceHeaders(h, src);
    expect(h.get("X-Request-ID")).toBe("bff-fixed");
    expect(h.get("X-Correlation-ID")).toBe("bff-fixed");
  });
});
