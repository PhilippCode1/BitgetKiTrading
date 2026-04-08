import type { LiveDataLineageSegment } from "@/lib/types";

export type LineageSegmentLabels = {
  label: string;
  producer: string;
  whyEmpty: string;
  nextStep: string;
};

/** UI-Texte für ein data_lineage-Segment je Locale (Gateway liefert DE+EN). */
export function labelsForLineageSegment(
  seg: LiveDataLineageSegment,
  locale: "de" | "en",
): LineageSegmentLabels {
  if (locale === "en") {
    return {
      label: seg.label_en || seg.label_de || seg.segment_id,
      producer: seg.producer_en || seg.producer_de,
      whyEmpty: seg.why_empty_en || seg.why_empty_de,
      nextStep: seg.next_step_en || seg.next_step_de,
    };
  }
  return {
    label: seg.label_de || seg.label_en || seg.segment_id,
    producer: seg.producer_de || seg.producer_en,
    whyEmpty: seg.why_empty_de || seg.why_empty_en,
    nextStep: seg.next_step_de || seg.next_step_en,
  };
}

export function shadowLiveMatchCellAria(
  value: boolean | null | undefined,
): "unknown" | "match" | "mismatch" {
  if (value === true) return "match";
  if (value === false) return "mismatch";
  return "unknown";
}

export function violationEntryCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}
