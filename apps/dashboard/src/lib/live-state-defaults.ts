import type { LiveStateResponse } from "@/lib/types";

/**
 * SSR-/Client-Platzhalter wenn `fetchLiveState` fehlschlaegt — gleiche Pflichtfelder wie Gateway-Payload.
 * `live_state_contract_version: 0` = nicht vom Gateway (nur Dashboard).
 */
export function emptyLiveStateResponse(
  symbol: string,
  timeframe: string,
): LiveStateResponse {
  const tf = timeframe.trim();
  return {
    status: "degraded",
    message: null,
    empty_state: true,
    degradation_reason: "gateway_unavailable",
    next_step: null,
    live_state_contract_version: 0,
    symbol,
    timeframe: tf,
    server_ts_ms: Date.now(),
    candles: [],
    latest_signal: null,
    latest_feature: null,
    structure_state: null,
    latest_drawings: [],
    latest_news: [],
    paper_state: {
      open_positions: [],
      last_closed_trade: null,
      unrealized_pnl_usdt: 0,
      mark_price: null,
    },
    health: { db: "unknown", redis: "unknown" },
    online_drift: null,
    data_lineage: [],
    market_freshness: {
      status: "no_candles",
      timeframe: tf,
      stale_warn_ms: 900_000,
      candle: null,
      ticker: null,
    },
    demo_data_notice: { show_banner: false, reasons: [] },
  };
}
