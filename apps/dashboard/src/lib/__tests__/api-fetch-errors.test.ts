import {
  apiFetchErrorFromHttp,
  extractErrorDetailFromBody,
  isApiFetchError,
} from "@/lib/api-fetch-errors";

describe("api-fetch-errors", () => {
  it("extractErrorDetailFromBody reads string detail", () => {
    expect(extractErrorDetailFromBody(JSON.stringify({ detail: "x" }))).toBe(
      "x",
    );
  });

  it("apiFetchErrorFromHttp maps 401 to auth", () => {
    const e = apiFetchErrorFromHttp({
      path: "/v1/a",
      status: 401,
      bodyText: "{}",
    });
    expect(isApiFetchError(e)).toBe(true);
    expect(e.kind).toBe("auth");
    expect(e.status).toBe(401);
  });

  it("apiFetchErrorFromHttp maps 503 with schema hint", () => {
    const e = apiFetchErrorFromHttp({
      path: "/v1/a",
      status: 503,
      bodyText: JSON.stringify({ detail: "pending_migrations=2" }),
    });
    expect(e.kind).toBe("schema");
  });

  it("extractErrorDetailFromBody liest Produktions-Gateway error-Envelope", () => {
    const text = JSON.stringify({
      error: {
        code: "AUTHENTICATION_REQUIRED",
        message: "Authentication required.",
        status: 401,
        layer: "api-gateway",
      },
    });
    const d = extractErrorDetailFromBody(text);
    expect(d).toContain("Authentication required");
    expect(d).toContain("AUTHENTICATION_REQUIRED");
  });

  it("apiFetchErrorFromHttp liest code aus error-Objekt", () => {
    const e = apiFetchErrorFromHttp({
      path: "/v1/x",
      status: 422,
      bodyText: JSON.stringify({
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid request body.",
          status: 422,
          layer: "api-gateway",
        },
      }),
    });
    expect(e.code).toBe("VALIDATION_ERROR");
    expect(e.layer).toBe("api-gateway");
    expect(e.kind).toBe("validation");
  });
});
