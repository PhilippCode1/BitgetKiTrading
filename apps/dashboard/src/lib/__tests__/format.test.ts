import {
  formatDistancePctField,
  formatNum,
  formatPct01,
  formatTsMs,
} from "../format";

describe("format", () => {
  it("formatTsMs handles null", () => {
    expect(formatTsMs(null)).toBe("—");
  });

  it("formatTsMs handles zero", () => {
    expect(formatTsMs(0)).toBe("—");
  });

  it("formatNum formats with digits", () => {
    expect(formatNum(1.2345, 2)).toMatch(/1[,.]23/);
  });

  it("formatNum handles NaN", () => {
    expect(formatNum(Number.NaN, 2)).toBe("—");
  });

  it("formatPct01 converts 0–1 to percent string", () => {
    expect(formatPct01(0.5)).toContain("50");
    expect(formatPct01(0.5)).toContain("%");
  });

  it("formatPct01 handles missing", () => {
    expect(formatPct01(undefined)).toBe("—");
  });

  it("formatDistancePctField treats small values as fraction", () => {
    const s = formatDistancePctField(0.01, 3);
    expect(s).toContain("%");
    expect(s).toMatch(/1[,.]000/);
  });

  it("formatDistancePctField treats 1<n<=100 as percent points", () => {
    const s = formatDistancePctField(1.5, 2);
    expect(s).toContain("%");
    expect(s).toMatch(/1[,.]50/);
  });

  it("formatDistancePctField handles missing", () => {
    expect(formatDistancePctField(undefined, 2)).toBe("—");
  });
});
