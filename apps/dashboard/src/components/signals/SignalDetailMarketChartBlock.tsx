"use client";

import { ConsoleLiveMarketChartSection } from "@/components/console/ConsoleLiveMarketChartSection";
import { useSignalDetailLlmChartOptional } from "@/components/signals/signal-detail-llm-chart-context";
import type { ExecutionPathViewModel } from "@/lib/execution-path-view-model";
import { consolePath } from "@/lib/console-paths";

type Props = Readonly<{
  signalId: string;
  symbol: string;
  timeframe: string;
  executionVm?: ExecutionPathViewModel | null;
  executionModeLabel?: string | null;
}>;

export function SignalDetailMarketChartBlock({
  signalId,
  symbol,
  timeframe,
  executionVm = null,
  executionModeLabel = null,
}: Props) {
  const pathname = consolePath(`signals/${signalId}`);
  const urlParams: Record<string, string> = { timeframe };
  const llm = useSignalDetailLlmChartOptional();
  return (
    <ConsoleLiveMarketChartSection
      pathname={pathname}
      urlParams={urlParams}
      chartSymbol={symbol}
      chartTimeframe={timeframe}
      symbolOptions={[symbol]}
      hideSymbolPicker
      executionVm={executionVm}
      executionModeLabel={executionModeLabel}
      chartSurfaceId="signal_detail"
      panelTitleKey="pages.signalsDetail.chartTitle"
      llmChartIntegration={llm != null}
      llmChartAnnotationsRaw={llm?.annotationsRaw ?? null}
      llmChartLayerEnabled={llm?.layerEnabled ?? true}
      onLlmChartLayerEnabledChange={llm?.setLayerEnabled}
      llmChartRationaleDe={llm?.rationaleDe ?? null}
    />
  );
}
