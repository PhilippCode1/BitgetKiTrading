import { summarizeReasonsJsonForUi } from "@/lib/signal-explain-display";

describe("summarizeReasonsJsonForUi", () => {
  it("returns empty for null", () => {
    expect(summarizeReasonsJsonForUi(null)).toEqual([]);
  });

  it("maps string array", () => {
    expect(summarizeReasonsJsonForUi(["a", "b"])).toEqual(["a", "b"]);
  });

  it("extracts reason field from objects", () => {
    expect(
      summarizeReasonsJsonForUi([{ reason: "stop too tight" }, { code: "x" }]),
    ).toEqual(["stop too tight", "x"]);
  });
});
