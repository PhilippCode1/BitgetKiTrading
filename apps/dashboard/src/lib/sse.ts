export type LiveSseHandlers = {
  onCandle?: (data: unknown) => void;
  onSignal?: (data: unknown) => void;
  onDrawing?: (data: unknown) => void;
  onNews?: (data: unknown) => void;
  onPaper?: (data: unknown) => void;
  /** Market-Stream: ``market_feed_health`` via Gateway -> SSE event ``feed_health`` */
  onFeedHealth?: (data: unknown) => void;
  onPing?: () => void;
  onError?: () => void;
};

/** Same-origin BFF-URL fuer Live-SSE (Authorization nur serverseitig im Route-Handler). */
export function buildLiveStreamUrl(symbol: string, timeframe: string): URL {
  const u = new URL("/api/dashboard/live/stream", window.location.origin);
  u.searchParams.set("symbol", symbol);
  u.searchParams.set("timeframe", timeframe);
  return u;
}

/**
 * Einmaliger EventSource ohne Reconnect/Heartbeat (Legacy/Demos).
 * Produktions-Pfad: `startManagedLiveEventSource` (Backoff, 15s-Ping-Watch, globaler UI-Status).
 */
export function openLiveEventSource(
  symbol: string,
  timeframe: string,
  handlers: LiveSseHandlers,
): EventSource | null {
  if (typeof window === "undefined" || typeof EventSource === "undefined") {
    return null;
  }
  const u = buildLiveStreamUrl(symbol, timeframe);
  const es = new EventSource(u.toString());
  const wrap = (fn?: (data: unknown) => void) => (ev: MessageEvent<string>) => {
    try {
      fn?.(JSON.parse(ev.data));
    } catch {
      fn?.(ev.data);
    }
  };
  es.addEventListener("candle", wrap(handlers.onCandle));
  es.addEventListener("signal", wrap(handlers.onSignal));
  es.addEventListener("drawing", wrap(handlers.onDrawing));
  es.addEventListener("news", wrap(handlers.onNews));
  es.addEventListener("paper", wrap(handlers.onPaper));
  es.addEventListener("feed_health", wrap(handlers.onFeedHealth));
  es.addEventListener("ping", () => handlers.onPing?.());
  es.onerror = () => {
    handlers.onError?.();
    es.close();
  };
  return es;
}
