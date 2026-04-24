/**
 * Typisierung gemaess shared/contracts/schemas/payload_candle_close.schema.json
 * (Kernfelder: start_ts_ms, open, high, low, close; optional: usdt_vol, quote_vol).
 */
export type PayloadCandleClose = Readonly<{
  start_ts_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  usdt_vol?: number;
  quote_vol?: number;
}>;

function finiteNum(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/**
 * Eingehende Events (z. B. market-stream) auf Schema-Shape mappen, sonst null.
 * Unterstuetzt auch LiveCandle-Shape (time_s in Sekunden) per Konvertierung.
 */
export function parsePayloadCandleClose(
  raw: unknown,
): PayloadCandleClose | null {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const o = raw as Record<string, unknown>;
  if (finiteNum(o.start_ts_ms) && finiteNum(o.open) && finiteNum(o.high) && finiteNum(o.low) && finiteNum(o.close)) {
    return {
      start_ts_ms: Math.trunc(o.start_ts_ms),
      open: o.open,
      high: o.high,
      low: o.low,
      close: o.close,
      ...(finiteNum(o.usdt_vol) ? { usdt_vol: o.usdt_vol } : {}),
      ...(finiteNum(o.quote_vol) ? { quote_vol: o.quote_vol } : {}),
    };
  }
  if (
    finiteNum(o.time_s) &&
    finiteNum(o.open) &&
    finiteNum(o.high) &&
    finiteNum(o.low) &&
    finiteNum(o.close)
  ) {
    const tMs = Math.floor(o.time_s * 1000);
    const vol = finiteNum(o.volume_usdt) ? o.volume_usdt : o.volume;
    return {
      start_ts_ms: tMs,
      open: o.open,
      high: o.high,
      low: o.low,
      close: o.close,
      ...(finiteNum(vol) ? { usdt_vol: vol } : {}),
    };
  }
  return null;
}

export const TICKER_LABEL_THROTTLE_MS = 100;

/** Fuer gespiegelte React-Listen (LiveCandle) neben dem imperativen Chart-Update. */
export function liveCandleFromPayload(p: PayloadCandleClose) {
  return {
    time_s: Math.trunc(p.start_ts_ms / 1000),
    open: p.open,
    high: p.high,
    low: p.low,
    close: p.close,
    volume_usdt:
      typeof p.usdt_vol === "number" && Number.isFinite(p.usdt_vol)
        ? p.usdt_vol
        : 0,
  };
}
