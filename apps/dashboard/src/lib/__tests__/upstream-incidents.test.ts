import {
  aggregateOpsFetchFailures,
  fingerprintFetchErrorMessage,
  severityForTransportKind,
} from "@/lib/upstream-incidents";

describe("fingerprintFetchErrorMessage", () => {
  it("groups different v1 paths (incl. query) when connectivity signals match", () => {
    const a = fingerprintFetchErrorMessage(
      "GET /v1/system/health?x=1 — HTTP 503",
    );
    const b = fingerprintFetchErrorMessage("GET /v1/foo/bar — HTTP 503");
    expect(a).toBe(b);
    expect(a).toContain("shared connectivity");
  });

  it("collapses ECONNREFUSED style messages to shared bucket", () => {
    const fp = fingerprintFetchErrorMessage(
      "GET /v1/models — API_GATEWAY_URL unreachable ECONNREFUSED",
    );
    expect(fp).toContain("shared connectivity");
  });
});

describe("aggregateOpsFetchFailures", () => {
  it("creates transport cascade for a single unreachable module", () => {
    const agg = aggregateOpsFetchFailures([
      { id: "health", error: "GET /v1/x — nicht erreichbar" },
      { id: "liveState", error: null },
    ]);
    expect(agg.transportCascade).not.toBeNull();
    expect(agg.transportCascade?.count).toBe(1);
    expect(agg.transportCascade?.severity).toBe("degraded");
    expect(agg.suppressedModules.has("health")).toBe(true);
  });

  it("does not cascade a single timeout without second module", () => {
    const agg = aggregateOpsFetchFailures([
      { id: "health", error: "GET /v1/x — timeout" },
    ]);
    expect(agg.transportCascade).toBeNull();
  });

  it("cascades two timeouts with same fingerprint", () => {
    const msg = "GET /v1/a — Request timed out (5000ms)";
    const agg = aggregateOpsFetchFailures([
      { id: "health", error: msg },
      { id: "liveState", error: msg },
    ]);
    expect(agg.transportCascade).not.toBeNull();
    expect(agg.transportCascade?.kind).toBe("timeout");
  });

  it("marks auth failures as blocker severity", () => {
    const agg = aggregateOpsFetchFailures([
      { id: "health", error: "HTTP 401" },
    ]);
    expect(agg.transportCascade?.severity).toBe("blocker");
  });
});

describe("severityForTransportKind", () => {
  it("classifies forbidden as blocker", () => {
    expect(severityForTransportKind("forbidden")).toBe("blocker");
  });
});
