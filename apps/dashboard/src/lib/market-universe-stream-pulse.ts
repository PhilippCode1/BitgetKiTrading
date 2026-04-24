/**
 * Market-Universe: Pipeline-Lag (feed_health) + VPIN-Sparkline — reine Hilfsfunktionen.
 */

export type FeedHealthSsePayload = {
  event_type?: string;
  symbol?: string;
  exchange_ts_ms?: number | null;
  processed_ts_ms?: number | null;
  pipeline_lag_ms?: number | null;
  age_ticker_ms?: number | null;
  vpin_toxicity_0_1?: number | null;
  ok?: boolean;
  payload?: Record<string, unknown>;
};

export const VPIN_SPARKLINE_MAX = 64;

export function effectivePipelineLagMs(p: FeedHealthSsePayload): number | null {
  const fromPayload = p.pipeline_lag_ms;
  if (fromPayload != null && Number.isFinite(fromPayload)) {
    return Math.max(0, Math.floor(fromPayload));
  }
  const ex = p.exchange_ts_ms;
  const pr = p.processed_ts_ms;
  if (
    ex != null &&
    pr != null &&
    Number.isFinite(ex) &&
    Number.isFinite(pr) &&
    pr >= ex
  ) {
    return Math.max(0, Math.floor(pr - ex));
  }
  const age = p.age_ticker_ms;
  if (age != null && Number.isFinite(age)) {
    return Math.max(0, Math.floor(age));
  }
  return null;
}

export type LagBucket = "ok" | "warn" | "bad" | "unknown";

/** Grün < 500 ms, Gelb < 2000 ms, Rot sonst. */
export function pipelineLagBucket(lagMs: number | null): LagBucket {
  if (lagMs == null || !Number.isFinite(lagMs)) return "unknown";
  if (lagMs < 500) return "ok";
  if (lagMs < 2000) return "warn";
  return "bad";
}

export function pushVpinHistory(
  prior: readonly number[],
  vpin: number | null,
): number[] {
  if (vpin == null || !Number.isFinite(vpin)) {
    return [...prior];
  }
  const v = Math.max(0, Math.min(1, vpin));
  const next = [...prior, v];
  if (next.length > VPIN_SPARKLINE_MAX) {
    return next.slice(next.length - VPIN_SPARKLINE_MAX);
  }
  return next;
}

export function vpinWarningLevel(
  vpin: number | null,
): "none" | "caution" | "halt" {
  if (vpin == null || !Number.isFinite(vpin)) return "none";
  if (vpin > 0.85) return "halt";
  if (vpin > 0.7) return "caution";
  return "none";
}
