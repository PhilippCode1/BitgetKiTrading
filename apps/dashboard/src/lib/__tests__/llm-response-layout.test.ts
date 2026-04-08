import { splitExplanatoryText } from "@/lib/llm-response-layout";

describe("splitExplanatoryText", () => {
  it("splits two short paragraphs", () => {
    const r = splitExplanatoryText(
      "Erste Zeile.\n\nZweiter Block.\nNoch eine.",
    );
    expect(r.summary).toBe("Erste Zeile.");
    expect(r.detail).toContain("Zweiter Block.");
  });

  it("single short paragraph has no detail", () => {
    const r = splitExplanatoryText("Nur ein Absatz.");
    expect(r.summary).toBe("Nur ein Absatz.");
    expect(r.detail).toBe("");
  });

  it("long block takes first sentence as summary when over limit", () => {
    const long = "A".repeat(600);
    const text = `Kurzer Satz davor. ${long}`;
    const r = splitExplanatoryText(text, 200);
    expect(r.summary).toContain("Kurzer Satz davor.");
    expect(r.detail.length).toBeGreaterThan(0);
  });

  it("trims and handles empty", () => {
    expect(splitExplanatoryText("   ")).toEqual({ summary: "", detail: "" });
    expect(splitExplanatoryText(null)).toEqual({ summary: "", detail: "" });
  });
});
