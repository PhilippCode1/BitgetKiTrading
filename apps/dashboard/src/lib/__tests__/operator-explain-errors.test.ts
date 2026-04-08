import {
  extractDetailFields,
  isOperatorExplainSuccessPayload,
  resolveNetworkFailure,
  resolveOperatorExplainFailure,
  sanitizePublicErrorMessage,
} from "@/lib/operator-explain-errors";

const t = (key: string, vars?: Record<string, string | number | boolean>) =>
  vars ? `${key}:${JSON.stringify(vars)}` : key;

describe("sanitizePublicErrorMessage", () => {
  it("truncates long strings", () => {
    const s = "x".repeat(300);
    expect(sanitizePublicErrorMessage(s, 50).length).toBeLessThanOrEqual(51);
  });

  it("collapses whitespace", () => {
    expect(sanitizePublicErrorMessage("a  \n  b")).toBe("a b");
  });
});

describe("extractDetailFields", () => {
  it("reads code and message from object detail", () => {
    const body = JSON.stringify({ detail: { code: "X", message: "Y" } });
    expect(extractDetailFields(body)).toEqual({
      code: "X",
      message: "Y",
      failure_class: null,
    });
  });

  it("reads failure_class from detail", () => {
    const body = JSON.stringify({
      detail: { code: "LLM_UNAVAILABLE", failure_class: "circuit_open" },
    });
    expect(extractDetailFields(body)).toEqual({
      code: "LLM_UNAVAILABLE",
      message: null,
      failure_class: "circuit_open",
    });
  });

  it("reads nested error envelope", () => {
    const body = JSON.stringify({
      error: { code: "LLM_UNAVAILABLE", message: "upstream" },
    });
    expect(extractDetailFields(body)).toEqual({
      code: "LLM_UNAVAILABLE",
      message: "upstream",
      failure_class: null,
    });
  });
});

describe("resolveOperatorExplainFailure", () => {
  it("maps 401", () => {
    expect(resolveOperatorExplainFailure(401, "{}", t)).toBe(
      "pages.health.aiExplainErrAuth",
    );
  });

  it("maps 503 LLM orchestrator config", () => {
    const b = JSON.stringify({
      detail: { code: "LLM_ORCH_UNAVAILABLE", message: "x" },
    });
    expect(resolveOperatorExplainFailure(503, b, t)).toBe(
      "pages.health.aiExplainErrOrchestratorConfig",
    );
  });

  it("maps 502 OpenAI key hint", () => {
    const b = JSON.stringify({
      detail: {
        code: "LLM_UNAVAILABLE",
        message: "OpenAI: OPENAI_API_KEY fehlt",
      },
    });
    expect(resolveOperatorExplainFailure(502, b, t)).toBe(
      "pages.health.aiExplainErrOpenaiKey",
    );
  });

  it("maps 400 CONTEXT_JSON_TOO_LARGE", () => {
    const b = JSON.stringify({
      detail: { code: "CONTEXT_JSON_TOO_LARGE", message: "too big" },
    });
    expect(resolveOperatorExplainFailure(400, b, t)).toBe(
      "pages.health.aiExplainErrContextTooLarge",
    );
  });

  it("maps 502 circuit_open via failure_class", () => {
    const b = JSON.stringify({
      detail: {
        code: "LLM_UNAVAILABLE",
        failure_class: "circuit_open",
        message: "x",
      },
    });
    expect(resolveOperatorExplainFailure(502, b, t)).toBe(
      "pages.health.aiExplainErrCircuitOpen",
    );
  });

  it("maps 502 no_provider_configured", () => {
    const b = JSON.stringify({
      detail: {
        code: "LLM_UNAVAILABLE",
        failure_class: "no_provider_configured",
      },
    });
    expect(resolveOperatorExplainFailure(502, b, t)).toBe(
      "pages.health.aiExplainErrProviderNotConfigured",
    );
  });

  it("maps 502 retry_exhausted", () => {
    const b = JSON.stringify({
      detail: {
        code: "LLM_UNAVAILABLE",
        failure_class: "retry_exhausted",
      },
    });
    expect(resolveOperatorExplainFailure(502, b, t)).toBe(
      "pages.health.aiExplainErrLlmRetryExhausted",
    );
  });

  it("detects HTML error page", () => {
    expect(resolveOperatorExplainFailure(502, "<!DOCTYPE html><html>", t)).toBe(
      "pages.health.aiExplainErrUnexpectedHtml",
    );
  });
});

describe("resolveNetworkFailure", () => {
  it("maps Failed to fetch", () => {
    expect(resolveNetworkFailure(new Error("Failed to fetch"), t)).toBe(
      "pages.health.aiExplainErrOffline",
    );
  });

  it("maps ECONNREFUSED", () => {
    expect(
      resolveNetworkFailure(new Error("fetch failed: ECONNREFUSED"), t),
    ).toBe("pages.health.aiExplainErrOffline");
  });

  it("returns null for unknown errors", () => {
    expect(resolveNetworkFailure(new Error("weird"), t)).toBeNull();
  });
});

describe("isOperatorExplainSuccessPayload", () => {
  it("accepts valid envelope", () => {
    expect(
      isOperatorExplainSuccessPayload({
        ok: true,
        result: { explanation_de: "Hallo" },
      }),
    ).toBe(true);
  });

  it("rejects empty explanation", () => {
    expect(
      isOperatorExplainSuccessPayload({
        ok: true,
        result: { explanation_de: "   " },
      }),
    ).toBe(false);
  });

  it("rejects missing result", () => {
    expect(isOperatorExplainSuccessPayload({ ok: true })).toBe(false);
  });
});
