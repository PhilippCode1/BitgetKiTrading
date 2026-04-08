import { ApiFetchError } from "@/lib/api-fetch-errors";
import {
  classifyFetchError,
  mapApiFetchKindToUi,
  translateFetchError,
} from "@/lib/user-facing-fetch-error";

describe("classifyFetchError", () => {
  it("maps ApiFetchError by kind", () => {
    const e = new ApiFetchError({
      kind: "auth",
      path: "/v1/x",
      message: "x",
    });
    expect(classifyFetchError(e)).toBe("unauthorized");
  });

  it("mapApiFetchKindToUi covers schema", () => {
    expect(mapApiFetchKindToUi("schema")).toBe("bad_gateway");
  });

  it("falls back to string heuristics", () => {
    expect(classifyFetchError(new Error("HTTP 502"))).toBe("bad_gateway");
  });

  it("classifies env / gateway setup hints as configuration", () => {
    expect(
      classifyFetchError(
        new Error("Set DASHBOARD_GATEWAY_AUTHORIZATION on the server"),
      ),
    ).toBe("configuration");
  });
});

describe("translateFetchError", () => {
  const echo = (key: string) => key;

  it("mapped HTTP 401 auf unauthorized-Textkeys", () => {
    const r = translateFetchError("upstream HTTP 401", echo);
    expect(r.title).toBe("ui.fetchError.unauthorized.title");
    expect(r.body).toBe("ui.fetchError.unauthorized.body");
    expect(r.refreshHint).toBe("ui.refreshHint");
  });

  it("mapped HTTP 503 auf bad_gateway-Textkeys", () => {
    const r = translateFetchError("HTTP 503", echo);
    expect(r.title).toBe("ui.fetchError.bad_gateway.title");
    expect(r.body).toBe("ui.fetchError.bad_gateway.body");
  });
});
