import type {
  StrategyOverlayModel,
  StrategyOverlayLayerId,
} from "@/lib/chart/strategy-overlay-model";
import type { LiveSignal } from "@/lib/types";

export type StrategyOverlayChartLine = Readonly<{
  id: StrategyOverlayLayerId;
  price: number;
  axisLabel: string;
  hint: string;
}>;

type TFn = (key: string, params?: Record<string, string | number>) => string;

export function formatChartPriceDe(price: number): string {
  return new Intl.NumberFormat("de-DE", {
    maximumFractionDigits: 8,
    minimumFractionDigits: 0,
  }).format(price);
}

export function buildStrategyOverlayChartLines(
  model: StrategyOverlayModel,
  signal: LiveSignal | null,
  t: TFn,
  formatPrice: (n: number) => string,
): StrategyOverlayChartLine[] {
  const refSrcKey =
    model.reference?.source === "mark_price"
      ? "ui.chart.strategy.refSourceMark"
      : model.reference?.source === "ticker_last"
        ? "ui.chart.strategy.refSourceTicker"
        : "ui.chart.strategy.refSourceClose";

  const refSrc = t(refSrcKey);

  return model.lines.map((line) => {
    const px = formatPrice(line.price);
    let axisLabel: string;
    let hint: string;

    switch (line.id) {
      case "reference":
        axisLabel = t("ui.chart.strategy.axisRef");
        hint = t("ui.chart.strategy.hintRef", { price: px, source: refSrc });
        break;
      case "stop_loss": {
        const pct = signal?.stop_distance_pct;
        axisLabel = t("ui.chart.strategy.axisStop");
        hint =
          pct != null && Number.isFinite(pct)
            ? t("ui.chart.strategy.hintStop", { price: px, pct })
            : t("ui.chart.strategy.hintStopNoPct", { price: px });
        break;
      }
      case "take_profit_mfe": {
        const bps = signal?.expected_mfe_bps;
        axisLabel = t("ui.chart.strategy.axisTp");
        hint =
          bps != null && Number.isFinite(bps)
            ? t("ui.chart.strategy.hintTp", { price: px, bps })
            : t("ui.chart.strategy.hintTpNoBps", { price: px });
        break;
      }
      case "risk_mae": {
        const bps = signal?.expected_mae_bps;
        axisLabel = t("ui.chart.strategy.axisMae");
        hint =
          bps != null && Number.isFinite(bps)
            ? t("ui.chart.strategy.hintMae", { price: px, bps })
            : t("ui.chart.strategy.hintMaeNoBps", { price: px });
        break;
      }
      case "stop_budget_max": {
        const pct = signal?.stop_budget_max_pct_allowed;
        axisLabel = t("ui.chart.strategy.axisBudgetMax");
        hint =
          pct != null && Number.isFinite(pct)
            ? t("ui.chart.strategy.hintBudgetMax", { price: px, pct })
            : t("ui.chart.strategy.hintBudgetMaxNoPct", { price: px });
        break;
      }
      case "stop_min_executable": {
        const pct = signal?.stop_min_executable_pct;
        axisLabel = t("ui.chart.strategy.axisMinExec");
        hint =
          pct != null && Number.isFinite(pct)
            ? t("ui.chart.strategy.hintMinExec", { price: px, pct })
            : t("ui.chart.strategy.hintMinExecNoPct", { price: px });
        break;
      }
      default: {
        axisLabel = line.id;
        hint = px;
      }
    }

    return { id: line.id, price: line.price, axisLabel, hint };
  });
}
