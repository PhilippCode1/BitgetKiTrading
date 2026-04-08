import {
  labelsForLineageSegment,
  shadowLiveMatchCellAria,
  violationEntryCount,
} from "@/lib/shadow-live-console";
import type { LiveDataLineageSegment } from "@/lib/types";

describe("shadow-live-console", () => {
  it("labelsForLineageSegment bevorzugt passende Locale", () => {
    const seg: LiveDataLineageSegment = {
      segment_id: "candles",
      label_de: "Kerzen",
      label_en: "Candles",
      has_data: false,
      producer_de: "Bitget",
      producer_en: "Bitget",
      why_empty_de: "Leer",
      why_empty_en: "Empty",
      next_step_de: "Warten",
      next_step_en: "Wait",
    };
    const de = labelsForLineageSegment(seg, "de");
    expect(de.label).toBe("Kerzen");
    expect(de.whyEmpty).toBe("Leer");
    const en = labelsForLineageSegment(seg, "en");
    expect(en.label).toBe("Candles");
    expect(en.whyEmpty).toBe("Empty");
  });

  it("shadowLiveMatchCellAria", () => {
    expect(shadowLiveMatchCellAria(true)).toBe("match");
    expect(shadowLiveMatchCellAria(false)).toBe("mismatch");
    expect(shadowLiveMatchCellAria(null)).toBe("unknown");
    expect(shadowLiveMatchCellAria(undefined)).toBe("unknown");
  });

  it("violationEntryCount", () => {
    expect(violationEntryCount(null)).toBe(0);
    expect(violationEntryCount([1, 2])).toBe(2);
  });
});
