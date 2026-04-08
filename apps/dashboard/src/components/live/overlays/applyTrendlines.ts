import type { IChartApi, ISeriesApi, LineData, Time } from "lightweight-charts";

export function ensureTrendlineSeries(
  chart: IChartApi,
  existing: ISeriesApi<"Line"> | null,
  color: string,
): ISeriesApi<"Line"> {
  if (existing) {
    chart.removeSeries(existing);
  }
  return chart.addLineSeries({
    color,
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: true,
  });
}

export function trendlineToLineData(tl: {
  t0_ms: number;
  p0: number;
  t1_ms: number;
  p1: number;
}): LineData[] {
  const t0 = Math.floor(tl.t0_ms / 1000) as Time;
  const t1 = Math.floor(tl.t1_ms / 1000) as Time;
  return [
    { time: t0, value: tl.p0 },
    { time: t1, value: tl.p1 },
  ];
}
