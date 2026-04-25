import type { LiveFeatureSnapshot, LiveMarketFreshness, LiveStateResponse } from "@/lib/types";

export type ChartWorkspaceAlert =
  | "none"
  | "no_candles_live_blocked"
  | "stale_live_blocked"
  | "asset_quarantined"
  | "bitget_unreachable";

const SECRET_MARKERS = [
  "authorization",
  "bearer",
  "token",
  "secret",
  "api_key",
  "password",
];

export function redactChartErrorDetail(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let text = raw.slice(0, 240);
  text = text.replace(/authorization\s*[:=]\s*bearer\s+\S+/gi, "authorization=***");
  text = text.replace(/bearer\s+\S+/gi, "bearer ***");
  for (const marker of SECRET_MARKERS) {
    const re = new RegExp(`${marker}\\s*[:=]\\s*\\S+`, "gi");
    text = text.replace(re, `${marker}=***`);
  }
  return text;
}

function isQuarantined(state: LiveStateResponse): boolean {
  const sigMeta = (state.latest_signal?.instrument_metadata || {}) as Record<string, unknown>;
  const status = String(sigMeta.trading_status || "").toLowerCase();
  return (
    status.includes("quarant") ||
    status.includes("suspend") ||
    status.includes("delist")
  );
}

function isBitgetUnreachable(
  health: LiveStateResponse["health"],
  freshness: LiveMarketFreshness | null,
): boolean {
  if (health.db !== "ok" || health.redis !== "ok") return false;
  return freshness?.status === "dead";
}

export function resolveChartWorkspaceAlert(
  state: LiveStateResponse,
  fetchErr: string | null,
): ChartWorkspaceAlert {
  if (fetchErr) return "bitget_unreachable";
  const freshness = state.market_freshness ?? null;
  if (isQuarantined(state)) return "asset_quarantined";
  if (state.candles.length === 0 || freshness?.status === "no_candles") {
    return "no_candles_live_blocked";
  }
  if (freshness?.status === "stale") return "stale_live_blocked";
  if (isBitgetUnreachable(state.health, freshness)) return "bitget_unreachable";
  return "none";
}

export function chartWorkspaceAlertText(alert: ChartWorkspaceAlert): string | null {
  if (alert === "no_candles_live_blocked") {
    return "Keine Marktdaten verfuegbar, Live blockiert.";
  }
  if (alert === "stale_live_blocked") {
    return "Daten veraltet, keine Live-Freigabe.";
  }
  if (alert === "asset_quarantined") {
    return "Asset in Quarantaene.";
  }
  if (alert === "bitget_unreachable") {
    return "Bitget-Datenquelle nicht erreichbar.";
  }
  return null;
}

export function buildRiskStatusLabel(state: LiveStateResponse): string {
  const action = (state.latest_signal?.trade_action || "").toLowerCase();
  if (action === "allow_trade") return "Risikostatus: beobachtbar";
  if (action === "do_not_trade") return "Risikostatus: blockiert";
  if (action) return `Risikostatus: ${action}`;
  return "Risikostatus: unbekannt";
}

export function buildDataQualityHint(feature: LiveFeatureSnapshot | null | undefined): string {
  if (!feature) return "Datenqualitaet unbekannt";
  const status = (feature.feature_quality_status || "").toLowerCase();
  if (!status || status.includes("unknown")) return "Datenqualitaet unbekannt";
  if (status.includes("ok")) return "Datenqualitaet ok";
  return "Datenqualitaet eingeschraenkt";
}

export function buildLiquiditySpreadHint(
  feature: LiveFeatureSnapshot | null | undefined,
): string {
  if (!feature) return "Liquiditaet/Spread unbekannt";
  const spread = feature.spread_bps;
  const depth = feature.depth_to_bar_volume_ratio;
  const spreadLabel = typeof spread === "number" ? `${spread.toFixed(1)} bps` : "—";
  const depthLabel = typeof depth === "number" ? depth.toFixed(2) : "—";
  return `Spread ${spreadLabel} · Liquiditaet ${depthLabel}`;
}
