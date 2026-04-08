import { formatApiErrorDetail } from "@/lib/api-error-detail";

describe("formatApiErrorDetail", () => {
  it("returns string detail", () => {
    expect(formatApiErrorDetail('{"detail":"fehlt"}')).toBe("fehlt");
  });

  it("returns object detail.message", () => {
    expect(
      formatApiErrorDetail(
        JSON.stringify({
          detail: {
            code: "LLM_ORCH_UNAVAILABLE",
            message: "INTERNAL_API_KEY fehlt",
          },
        }),
      ),
    ).toBe("LLM_ORCH_UNAVAILABLE: INTERNAL_API_KEY fehlt");
  });

  it("returns object detail.message without code prefix when code missing", () => {
    expect(
      formatApiErrorDetail(JSON.stringify({ detail: { message: "nur text" } })),
    ).toBe("nur text");
  });

  it("falls back to raw text for non-JSON", () => {
    expect(formatApiErrorDetail("plain error")).toBe("plain error");
  });

  it("handles validation array detail", () => {
    const s = JSON.stringify({
      detail: [{ loc: ["body", "x"], msg: "invalid" }],
    });
    expect(formatApiErrorDetail(s)).toContain("invalid");
  });
});
