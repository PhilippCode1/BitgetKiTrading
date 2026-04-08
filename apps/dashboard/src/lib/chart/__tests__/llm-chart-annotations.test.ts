import {
  candleStatsFromBars,
  normalizeUnixSecondsForChart,
  sanitizeLlmChartAnnotations,
  sanitizeLlmChartAnnotationsDetailed,
} from "@/lib/chart/llm-chart-annotations";

const stats = { timeMin: 1_000, timeMax: 2_000, priceMin: 100, priceMax: 200 };

describe("sanitizeLlmChartAnnotations", () => {
  it("returns empty for non-object", () => {
    expect(sanitizeLlmChartAnnotations(null, stats)).toEqual({
      horizontalLines: [],
      priceBands: [],
      markers: [],
      lineSegments: [],
      verticalRules: [],
      uncertaintyRegions: [],
      notes: [],
    });
  });

  it("extracts notes even if schema_version wrong", () => {
    const r = sanitizeLlmChartAnnotations(
      {
        schema_version: "9.9",
        chart_notes_de: [{ text: "  Nur Notiz  " }],
      },
      stats,
    );
    expect(r.notes).toEqual(["Nur Notiz"]);
    expect(r.markers).toHaveLength(0);
  });

  it("accepts horizontal line in range", () => {
    const r = sanitizeLlmChartAnnotations(
      {
        schema_version: "1.0",
        horizontal_lines: [{ price: 150, label: "Support" }],
      },
      stats,
    );
    expect(r.horizontalLines).toHaveLength(1);
    expect(r.horizontalLines[0]!.price).toBe(150);
  });

  it("drops absurd prices", () => {
    const r = sanitizeLlmChartAnnotations(
      {
        schema_version: "1.0",
        horizontal_lines: [{ price: 1_000_000 }],
      },
      stats,
    );
    expect(r.horizontalLines).toHaveLength(0);
  });

  it("ignores garbage nested fields without throwing", () => {
    const r = sanitizeLlmChartAnnotations(
      {
        schema_version: "1.0",
        horizontal_lines: "broken" as unknown as [],
        time_markers: [{ time_unix_s: "x" }],
        line_segments: null,
      } as unknown as Record<string, unknown>,
      stats,
    );
    expect(r.horizontalLines).toHaveLength(0);
    expect(r.markers).toHaveLength(0);
  });

  it("normalizes millisecond unix to seconds for markers", () => {
    const tMs = 1_500_000_000_000;
    const tSec = Math.trunc(tMs / 1000);
    const spanT = stats.timeMax - stats.timeMin;
    const tLo = stats.timeMin - spanT * 0.02;
    const tHi = stats.timeMax + spanT * 0.02;
    const clamped = Math.min(Math.max(tSec, tLo), tHi);
    const r = sanitizeLlmChartAnnotations(
      {
        schema_version: "1.0",
        time_markers: [{ time_unix_s: tMs, label: "x", shape: "circle" }],
      },
      stats,
    );
    expect(r.markers).toHaveLength(1);
    expect(r.markers[0]!.time).toBe(clamped);
  });

  it("detailed meta reports wrong schema and ms corrections", () => {
    const d = sanitizeLlmChartAnnotationsDetailed(
      {
        schema_version: "0.0",
        chart_notes_de: [{ text: "n" }],
      },
      stats,
    );
    expect(d.meta.wrongSchemaVersion).toBe(true);
    expect(d.meta.notesExtracted).toBe(1);

    const tMs = 1_500_000_000_000;
    const d2 = sanitizeLlmChartAnnotationsDetailed(
      {
        schema_version: "1.0",
        time_markers: [{ time_unix_s: tMs }],
      },
      stats,
    );
    expect(d2.meta.timestampsCorrectedFromMs).toBeGreaterThanOrEqual(1);
  });

  it("drops geometry outside strict price band but keeps notes", () => {
    const d = sanitizeLlmChartAnnotationsDetailed(
      {
        schema_version: "1.0",
        horizontal_lines: [{ price: 9_999_999 }],
        chart_notes_de: [{ text: "nur Text" }],
      },
      stats,
    );
    expect(d.model.horizontalLines).toHaveLength(0);
    expect(d.model.notes).toEqual(["nur Text"]);
    expect(d.meta.geometryCandidatesTotal).toBe(1);
    expect(d.meta.geometryKeptTotal).toBe(0);
  });
});

describe("normalizeUnixSecondsForChart", () => {
  it("passes through second timestamps", () => {
    expect(normalizeUnixSecondsForChart(1_700_000_000)).toEqual({
      sec: 1_700_000_000,
      correctedFromMs: false,
    });
  });

  it("converts typical ms timestamps", () => {
    const r = normalizeUnixSecondsForChart(1_700_000_000_000);
    expect(r.correctedFromMs).toBe(true);
    expect(r.sec).toBe(1_700_000_000);
  });
});

describe("candleStatsFromBars", () => {
  it("returns null for empty", () => {
    expect(candleStatsFromBars([])).toBeNull();
  });

  it("aggregates OHLC", () => {
    const s = candleStatsFromBars([
      { time_s: 10, open: 100, high: 110, low: 90, close: 105 },
      { time_s: 20, open: 105, high: 108, low: 100, close: 102 },
    ]);
    expect(s).toEqual({
      timeMin: 10,
      timeMax: 20,
      priceMin: 90,
      priceMax: 110,
    });
  });
});
