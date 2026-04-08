import type { ISeriesApi, SeriesMarker, Time } from "lightweight-charts";

import type { LiveNewsItem } from "@/lib/types";

export function buildNewsMarkers(news: LiveNewsItem[]): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];
  for (const n of news) {
    const ms = n.published_ts_ms;
    if (ms == null) continue;
    const t = Math.floor(ms / 1000) as Time;
    const label = (n.title ?? "News").slice(0, 16);
    markers.push({
      time: t,
      position: "aboveBar",
      color: "#d4bc6a",
      shape: "circle",
      text: label,
    });
  }
  return markers;
}

export function applyNewsMarkers(
  series: ISeriesApi<"Candlestick">,
  news: LiveNewsItem[],
  enabled: boolean,
): void {
  if (!enabled) {
    series.setMarkers([]);
    return;
  }
  series.setMarkers(buildNewsMarkers(news));
}
