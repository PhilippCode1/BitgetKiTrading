import {
  isStrategySignalExplainSuccessPayload,
  resolveStrategySignalExplainFailure,
} from "@/lib/strategy-signal-explain-errors";

const t = (key: string) => key;

describe("strategy-signal-explain-errors", () => {
  it("isStrategySignalExplainSuccessPayload akzeptiert fehlende Text-Erklaerung bei execution_authority=none", () => {
    expect(
      isStrategySignalExplainSuccessPayload({
        ok: true,
        result: { execution_authority: "none" },
      }),
    ).toBe(true);
  });

  it("lehnt ok=false und unzulaessige execution_authority ab", () => {
    expect(
      isStrategySignalExplainSuccessPayload({
        ok: true,
        result: { strategy_explanation_de: "x", execution_authority: "operator" },
      }),
    ).toBe(false);
    expect(
      isStrategySignalExplainSuccessPayload({
        ok: false,
        result: { strategy_explanation_de: "x" },
      }),
    ).toBe(false);
  });

  it("resolveStrategySignalExplainFailure maps 502 like operator explain", () => {
    const msg = resolveStrategySignalExplainFailure(
      502,
      JSON.stringify({ detail: { code: "LLM_UNAVAILABLE", message: "x" } }),
      t,
    );
    expect(msg).toBe("pages.health.aiExplainErrLlmUnavailable");
  });
});
