import {
  mergeConsoleChartSearch,
  normalizeChartSymbolCookie,
  normalizeChartTimeframe,
} from "@/lib/chart-prefs";

describe("chart-prefs", () => {
  it("normalizes allowed timeframes", () => {
    expect(normalizeChartTimeframe("5M")).toBe("5m");
    expect(normalizeChartTimeframe("5m")).toBe("5m");
    expect(normalizeChartTimeframe("2h")).toBeNull();
  });

  it("normalizes symbol cookie", () => {
    expect(normalizeChartSymbolCookie("btc-usdt")).toBe("BTCUSDT");
    expect(normalizeChartSymbolCookie("ab")).toBeNull();
  });

  it("merges chart search preserving filters", () => {
    const href = mergeConsoleChartSearch(
      "/console/signals",
      { a: "1", symbol: "OLD" },
      { symbol: "BTCUSDT" },
    );
    expect(href).toContain("symbol=BTCUSDT");
    expect(href).toContain("a=1");
  });
});
