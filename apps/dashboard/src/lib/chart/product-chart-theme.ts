import {
  ColorType,
  type ChartOptions,
  type DeepPartial,
} from "lightweight-charts";

/**
 * TradingView lightweight-charts braucht konkrete Farben — abgestimmt auf {@link theme.css}.
 */
export const PRODUCT_CHART_COLORS = {
  background: "#0a0a0c", // --bg-surface
  text: "#ebe6db", // --fg-default
  grid: "rgba(212, 188, 106, 0.11)", // gold-tinted grid
  border: "rgba(212, 188, 106, 0.28)", // --border-default
  up: "#6bc98f", // --ok
  down: "#e07070", // --danger
  volumeUp: "rgba(107, 201, 143, 0.45)",
  volumeDown: "rgba(224, 112, 112, 0.45)",
  lineAccent: "#d4bc6a", // --accent
  mutedLine: "#a39a8c", // --fg-muted
  /** KI-Interpretations-Layer (nicht deterministisches Signal) */
  llmLine: "rgba(167, 139, 250, 0.92)",
  llmLineMuted: "rgba(167, 139, 250, 0.45)",
  llmMarker: "#c4b5fd",
  /** Widerstand / Supply-Zone (Short) */
  llmZoneResistanceTopFill1: "rgba(224, 112, 112, 0.4)",
  llmZoneResistanceTopFill2: "rgba(224, 112, 112, 0.08)",
  llmZoneResistanceTopLine: "rgba(224, 112, 112, 0.9)",
  /** Support / Demand-Zone */
  llmZoneSupportTopFill1: "rgba(107, 201, 143, 0.32)",
  llmZoneSupportTopFill2: "rgba(107, 201, 143, 0.08)",
  llmZoneSupportTopLine: "rgba(107, 201, 143, 0.9)",
  /** Unspezifische Box */
  llmZoneNeutralTopFill1: "rgba(167, 139, 250, 0.3)",
  llmZoneNeutralTopFill2: "rgba(167, 139, 250, 0.06)",
  llmZoneNeutralTopLine: "rgba(196, 181, 253, 0.85)",
} as const;

export type ProductChartTheme = typeof PRODUCT_CHART_COLORS;

export function buildProductChartOptions(
  overrides?: DeepPartial<ChartOptions>,
): DeepPartial<ChartOptions> {
  const base: DeepPartial<ChartOptions> = {
    layout: {
      background: {
        type: ColorType.Solid,
        color: PRODUCT_CHART_COLORS.background,
      },
      textColor: PRODUCT_CHART_COLORS.text,
      fontSize: 12,
      fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    },
    grid: {
      vertLines: { color: PRODUCT_CHART_COLORS.grid },
      horzLines: { color: PRODUCT_CHART_COLORS.grid },
    },
    rightPriceScale: {
      borderColor: PRODUCT_CHART_COLORS.border,
      scaleMargins: { top: 0.08, bottom: 0.2 },
    },
    timeScale: {
      borderColor: PRODUCT_CHART_COLORS.border,
      timeVisible: true,
      secondsVisible: false,
    },
    crosshair: {
      mode: 1, // Normal
      vertLine: {
        color: PRODUCT_CHART_COLORS.border,
        labelBackgroundColor: PRODUCT_CHART_COLORS.background,
      },
      horzLine: {
        color: PRODUCT_CHART_COLORS.border,
        labelBackgroundColor: PRODUCT_CHART_COLORS.background,
      },
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: true,
    },
    handleScale: {
      axisPressedMouseMove: { time: true, price: true },
      mouseWheel: true,
      pinch: true,
    },
    localization: {
      locale: typeof navigator !== "undefined" ? navigator.language : "de-DE",
    },
  };
  return deepMergeChartOptions(base, overrides ?? {});
}

function isPlainObject(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

/** Flaches Merge fuer ChartOptions (ausreichend fuer unsere Overrides). */
function deepMergeChartOptions(
  a: DeepPartial<ChartOptions>,
  b: DeepPartial<ChartOptions>,
): DeepPartial<ChartOptions> {
  const out: Record<string, unknown> = { ...a };
  for (const [k, bv] of Object.entries(b)) {
    const av = out[k];
    if (isPlainObject(av) && isPlainObject(bv)) {
      out[k] = deepMergeChartOptions(
        av as DeepPartial<ChartOptions>,
        bv as DeepPartial<ChartOptions>,
      ) as unknown;
    } else {
      out[k] = bv;
    }
  }
  return out as DeepPartial<ChartOptions>;
}
