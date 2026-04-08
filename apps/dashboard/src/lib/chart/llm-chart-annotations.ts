import type { LineData, SeriesMarker, Time } from "lightweight-charts";

import { PRODUCT_CHART_COLORS } from "@/lib/chart/product-chart-theme";
import type { ProductCandleBar } from "@/lib/chart/map-candles";

export type LlmLineStyleName = "solid" | "dashed" | "dotted";

export type SanitizedLlmChartAnnotations = Readonly<{
  horizontalLines: ReadonlyArray<{
    price: number;
    label?: string;
    lineStyle: 0 | 1 | 2 | 3;
  }>;
  priceBands: ReadonlyArray<{
    priceHigh: number;
    priceLow: number;
    label?: string;
    lineStyle: 0 | 1 | 2 | 3;
  }>;
  markers: SeriesMarker<Time>[];
  lineSegments: ReadonlyArray<{
    points: LineData<Time>[];
    lineStyle: 0 | 1 | 2 | 3;
    label?: string;
  }>;
  verticalRules: ReadonlyArray<{
    points: LineData<Time>[];
    lineStyle: 0 | 1 | 2 | 3;
    label?: string;
  }>;
  uncertaintyRegions: ReadonlyArray<{
    points: LineData<Time>[];
    label?: string;
  }>;
  notes: string[];
}>;

/** Transparenz fuer UI: was beim Sanitizen passiert ist (keine Secrets). */
export type LlmChartAnnotationSanitizeMeta = Readonly<{
  wrongSchemaVersion: boolean;
  skippedGeometryNoStats: boolean;
  notesExtracted: number;
  /** Unix-Zeiten, die vermutlich in ms kamen und auf Sekunden korrigiert wurden. */
  timestampsCorrectedFromMs: number;
  geometryCandidatesTotal: number;
  geometryKeptTotal: number;
}>;

export type SanitizeLlmChartAnnotationsDetailedResult = Readonly<{
  model: SanitizedLlmChartAnnotations;
  meta: LlmChartAnnotationSanitizeMeta;
}>;

const EMPTY: SanitizedLlmChartAnnotations = {
  horizontalLines: [],
  priceBands: [],
  markers: [],
  lineSegments: [],
  verticalRules: [],
  uncertaintyRegions: [],
  notes: [],
};

const EMPTY_META: LlmChartAnnotationSanitizeMeta = {
  wrongSchemaVersion: false,
  skippedGeometryNoStats: false,
  notesExtracted: 0,
  timestampsCorrectedFromMs: 0,
  geometryCandidatesTotal: 0,
  geometryKeptTotal: 0,
};

function mapLineStyle(s: unknown): 0 | 1 | 2 | 3 {
  if (s === "dotted") return 1;
  if (s === "dashed") return 2;
  return 0;
}

function isRecord(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function finiteNum(x: unknown): number | null {
  if (typeof x !== "number" || !Number.isFinite(x)) return null;
  return x;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(Math.max(n, lo), hi);
}

function markerShape(
  s: unknown,
): "arrowDown" | "arrowUp" | "circle" | "square" {
  if (s === "arrow_down") return "arrowDown";
  if (s === "arrow_up") return "arrowUp";
  if (s === "square") return "square";
  return "circle";
}

/**
 * Kerzen nutzen Unix-Sekunden. Modelle liefern gelegentlich Millisekunden.
 * Schwelle 1e11: sicher oberhalb sinnvoller Sekunden-Timestamps, unter typischer ms.
 */
export function normalizeUnixSecondsForChart(v: unknown): {
  sec: number | null;
  correctedFromMs: boolean;
} {
  const n = finiteNum(v);
  if (n === null) return { sec: null, correctedFromMs: false };
  let x = n;
  let corrected = false;
  if (x > 1e11) {
    x = Math.trunc(x / 1000);
    corrected = true;
  }
  const sec = Math.trunc(x);
  if (!Number.isFinite(sec)) return { sec: null, correctedFromMs: false };
  return { sec, correctedFromMs: corrected };
}

export function candleStatsFromBars(bars: readonly ProductCandleBar[]): {
  timeMin: number;
  timeMax: number;
  priceMin: number;
  priceMax: number;
} | null {
  if (!bars.length) return null;
  let timeMin = Infinity;
  let timeMax = -Infinity;
  let priceMin = Infinity;
  let priceMax = -Infinity;
  for (const b of bars) {
    if (!Number.isFinite(b.time_s)) continue;
    timeMin = Math.min(timeMin, b.time_s);
    timeMax = Math.max(timeMax, b.time_s);
    for (const p of [b.low, b.high, b.open, b.close]) {
      if (typeof p === "number" && Number.isFinite(p)) {
        priceMin = Math.min(priceMin, p);
        priceMax = Math.max(priceMax, p);
      }
    }
  }
  if (!Number.isFinite(timeMin) || !Number.isFinite(priceMin)) return null;
  return { timeMin, timeMax, priceMin, priceMax };
}

function emptyWithMeta(
  partial: Partial<LlmChartAnnotationSanitizeMeta>,
): SanitizeLlmChartAnnotationsDetailedResult {
  return {
    model: EMPTY,
    meta: { ...EMPTY_META, ...partial },
  };
}

/**
 * Wie {@link sanitizeLlmChartAnnotations}, plus Meta fuer UI-Hinweise (z. B. ms-Korrektur, verworfene Geometrie).
 */
export function sanitizeLlmChartAnnotationsDetailed(
  raw: unknown,
  stats: {
    timeMin: number;
    timeMax: number;
    priceMin: number;
    priceMax: number;
  } | null,
): SanitizeLlmChartAnnotationsDetailedResult {
  let tsCorrected = 0;
  try {
    if (raw === null || raw === undefined) {
      return emptyWithMeta({});
    }
    if (!isRecord(raw)) {
      return emptyWithMeta({});
    }

    const notes: string[] = [];
    const na = raw.chart_notes_de;
    if (Array.isArray(na)) {
      for (const item of na.slice(0, 8)) {
        if (!isRecord(item)) continue;
        const tx = item.text;
        if (typeof tx === "string") {
          const t = tx.trim().slice(0, 220);
          if (t.length > 0) notes.push(t);
        }
      }
    }

    if (raw.schema_version !== "1.0") {
      return {
        model: { ...EMPTY, notes },
        meta: {
          ...EMPTY_META,
          wrongSchemaVersion: true,
          notesExtracted: notes.length,
        },
      };
    }

    if (
      !stats ||
      stats.timeMax < stats.timeMin ||
      stats.priceMax < stats.priceMin
    ) {
      return emptyWithMeta({
        skippedGeometryNoStats: true,
        notesExtracted: notes.length,
      });
    }

    const spanT = Math.max(1, stats.timeMax - stats.timeMin);
    const spanP = Math.max(1e-12, stats.priceMax - stats.priceMin);
    const tLo = stats.timeMin - spanT * 0.02;
    const tHi = stats.timeMax + spanT * 0.02;
    const pLo = stats.priceMin - spanP * 0.15;
    const pHi = stats.priceMax + spanP * 0.15;
    const pStrictLo = stats.priceMin - spanP * 0.08;
    const pStrictHi = stats.priceMax + spanP * 0.08;

    let candidates = 0;
    let kept = 0;

    const horizontalLines: Array<{
      price: number;
      label?: string;
      lineStyle: 0 | 1 | 2 | 3;
    }> = [];
    if (Array.isArray(raw.horizontal_lines)) {
      const slice = raw.horizontal_lines.slice(0, 12);
      candidates += slice.length;
      for (const row of slice) {
        if (!isRecord(row)) continue;
        const price = finiteNum(row.price);
        if (price === null || price < pStrictLo || price > pStrictHi) continue;
        const label =
          typeof row.label === "string"
            ? row.label.trim().slice(0, 80)
            : undefined;
        horizontalLines.push({
          price,
          label: label && label.length > 0 ? label : undefined,
          lineStyle: mapLineStyle(row.line_style),
        });
        kept += 1;
      }
    }

    const priceBands: Array<{
      priceHigh: number;
      priceLow: number;
      label?: string;
      lineStyle: 0 | 1 | 2 | 3;
    }> = [];
    if (Array.isArray(raw.price_bands)) {
      const slice = raw.price_bands.slice(0, 8);
      candidates += slice.length;
      for (const row of slice) {
        if (!isRecord(row)) continue;
        const hi = finiteNum(row.price_high);
        const lo = finiteNum(row.price_low);
        if (hi === null || lo === null) continue;
        const top = Math.max(hi, lo);
        const bot = Math.min(hi, lo);
        if (top < pStrictLo || bot > pStrictHi) continue;
        const label =
          typeof row.label === "string"
            ? row.label.trim().slice(0, 80)
            : undefined;
        priceBands.push({
          priceHigh: clamp(top, pLo, pHi),
          priceLow: clamp(bot, pLo, pHi),
          label: label && label.length > 0 ? label : undefined,
          lineStyle: mapLineStyle(row.line_style),
        });
        kept += 1;
      }
    }

    const markers: SeriesMarker<Time>[] = [];
    if (Array.isArray(raw.time_markers)) {
      const slice = raw.time_markers.slice(0, 24);
      candidates += slice.length;
      for (const row of slice) {
        if (!isRecord(row)) continue;
        const nt = normalizeUnixSecondsForChart(row.time_unix_s);
        if (nt.correctedFromMs) tsCorrected += 1;
        const ts = nt.sec;
        if (ts === null) continue;
        const t = clamp(ts, tLo, tHi) as Time;
        const label =
          typeof row.label === "string" ? row.label.trim().slice(0, 64) : "";
        const sh = markerShape(row.shape);
        const up = sh === "arrowUp";
        markers.push({
          time: t,
          position: up ? "aboveBar" : "belowBar",
          color: PRODUCT_CHART_COLORS.llmMarker,
          shape: sh,
          text: label,
        });
        kept += 1;
      }
    }

    const lineSegments: Array<{
      points: LineData<Time>[];
      lineStyle: 0 | 1 | 2 | 3;
      label?: string;
    }> = [];
    if (Array.isArray(raw.line_segments)) {
      const slice = raw.line_segments.slice(0, 16);
      candidates += slice.length;
      for (const row of slice) {
        if (!isRecord(row)) continue;
        const naT = normalizeUnixSecondsForChart(row.time_a_unix_s);
        const nbT = normalizeUnixSecondsForChart(row.time_b_unix_s);
        if (naT.correctedFromMs) tsCorrected += 1;
        if (nbT.correctedFromMs) tsCorrected += 1;
        const ta = naT.sec;
        const tb = nbT.sec;
        const pa = finiteNum(row.price_a);
        const pb = finiteNum(row.price_b);
        if (ta === null || tb === null || pa === null || pb === null) continue;
        const t1 = clamp(ta, tLo, tHi) as Time;
        const t2 = clamp(tb, tLo, tHi) as Time;
        const v1 = clamp(pa, pLo, pHi);
        const v2 = clamp(pb, pLo, pHi);
        if (t1 === t2 && v1 === v2) continue;
        const label =
          typeof row.label === "string"
            ? row.label.trim().slice(0, 64)
            : undefined;
        lineSegments.push({
          points: [
            { time: t1, value: v1 },
            { time: t2, value: v2 },
          ],
          lineStyle: mapLineStyle(row.line_style),
          label: label && label.length > 0 ? label : undefined,
        });
        kept += 1;
      }
    }

    const verticalRules: Array<{
      points: LineData<Time>[];
      lineStyle: 0 | 1 | 2 | 3;
      label?: string;
    }> = [];
    const vTick = Math.max(1, Math.min(3_600, Math.floor(spanT / 800) || 1));
    if (Array.isArray(raw.vertical_rules)) {
      const slice = raw.vertical_rules.slice(0, 12);
      candidates += slice.length;
      for (const row of slice) {
        if (!isRecord(row)) continue;
        const nt = normalizeUnixSecondsForChart(row.time_unix_s);
        if (nt.correctedFromMs) tsCorrected += 1;
        const ts = nt.sec;
        const pl = finiteNum(row.price_low);
        const ph = finiteNum(row.price_high);
        if (ts === null || pl === null || ph === null) continue;
        const top = Math.max(ph, pl);
        const bot = Math.min(ph, pl);
        const tA = clamp(ts, tLo, tHi) as Time;
        let tB = clamp(ts + vTick, tLo, tHi) as Time;
        if (tB === tA) {
          tB = clamp(ts + 1, tLo, tHi) as Time;
        }
        if (tB === tA) continue;
        const vHi = clamp(top, pLo, pHi);
        const vLo = clamp(bot, pLo, pHi);
        if (vHi === vLo) continue;
        const label =
          typeof row.label === "string"
            ? row.label.trim().slice(0, 64)
            : undefined;
        verticalRules.push({
          points: [
            { time: tA, value: vHi },
            { time: tB, value: vLo },
          ],
          lineStyle: mapLineStyle(row.line_style),
          label: label && label.length > 0 ? label : undefined,
        });
        kept += 1;
      }
    }

    const uncertaintyRegions: Array<{
      points: LineData<Time>[];
      label?: string;
    }> = [];
    if (Array.isArray(raw.uncertainty_regions)) {
      const slice = raw.uncertainty_regions.slice(0, 8);
      candidates += slice.length;
      for (const row of slice) {
        if (!isRecord(row)) continue;
        const nf = normalizeUnixSecondsForChart(row.time_from_unix_s);
        const nt = normalizeUnixSecondsForChart(row.time_to_unix_s);
        if (nf.correctedFromMs) tsCorrected += 1;
        if (nt.correctedFromMs) tsCorrected += 1;
        const tf = nf.sec;
        const tt = nt.sec;
        const ph = finiteNum(row.price_high);
        const pl = finiteNum(row.price_low);
        if (tf === null || tt === null || ph === null || pl === null) continue;
        const t0 = clamp(Math.min(tf, tt), tLo, tHi) as Time;
        const t1 = clamp(Math.max(tf, tt), tLo, tHi) as Time;
        const top = Math.max(ph, pl);
        const bot = Math.min(ph, pl);
        const vHi = clamp(top, pLo, pHi);
        const vLo = clamp(bot, pLo, pHi);
        if (t0 === t1 || vHi === vLo) continue;
        const label =
          typeof row.label === "string"
            ? row.label.trim().slice(0, 80)
            : undefined;
        uncertaintyRegions.push({
          points: [
            { time: t0, value: vHi },
            { time: t1, value: vHi },
            { time: t1, value: vLo },
            { time: t0, value: vLo },
            { time: t0, value: vHi },
          ],
          label: label && label.length > 0 ? label : undefined,
        });
        kept += 1;
      }
    }

    return {
      model: {
        horizontalLines,
        priceBands,
        markers,
        lineSegments,
        verticalRules,
        uncertaintyRegions,
        notes,
      },
      meta: {
        wrongSchemaVersion: false,
        skippedGeometryNoStats: false,
        notesExtracted: notes.length,
        timestampsCorrectedFromMs: tsCorrected,
        geometryCandidatesTotal: candidates,
        geometryKeptTotal: kept,
      },
    };
  } catch {
    return emptyWithMeta({});
  }
}

/**
 * Parst und begrenzt KI-Chart-Annotationen. Ohne Kerzen-Statistik werden nur chart_notes uebernommen;
 * Geometrie braucht gueltige Zeit-/Preisgrenzen — sonst leer (kein Throw).
 */
export function sanitizeLlmChartAnnotations(
  raw: unknown,
  stats: {
    timeMin: number;
    timeMax: number;
    priceMin: number;
    priceMax: number;
  } | null,
): SanitizedLlmChartAnnotations {
  return sanitizeLlmChartAnnotationsDetailed(raw, stats).model;
}
