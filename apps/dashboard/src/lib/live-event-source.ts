/**
 * Live-Terminal SSE: Reconnect mit Backoff, kein sofortiges Schliessen bei transienten Fehlern.
 * Nach jeder erfolgreichen Verbindung Callback fuer REST-Backfill (Luecken schliessen).
 */

import type { LiveSseHandlers } from "@/lib/sse";
import { buildLiveStreamUrl } from "@/lib/sse";

export type LiveStreamConnectionState =
  | "connecting"
  | "open"
  | "reconnecting"
  /** Keine weiteren Reconnects — UI soll auf HTTP-Polling verweisen. */
  | "given_up";

export type ManagedLiveEventSourceOptions = {
  symbol: string;
  timeframe: string;
  handlers: LiveSseHandlers;
  /** Erste und jede wiederhergestellte Verbindung — hier REST-State nachziehen. */
  onConnectionOpen?: () => void;
  onReconnectScheduled?: (info: { attempt: number; delayMs: number }) => void;
  onConnectionState?: (state: LiveStreamConnectionState) => void;
  /**
   * Nach so vielen aufeinanderfolgenden Fehlversuchen (ohne erfolgreiches onopen) Reconnect stoppen.
   * Default 22 — verhindert endlose Schleifen bei dauerhaftem 503/fehlendem Redis.
   */
  maxReconnectAttempts?: number;
  /** Einmalig, wenn maxReconnectAttempts erreicht (SSE wird nicht weiter versucht). */
  onGiveUp?: (info: { lastAttempt: number }) => void;
};

export type ManagedLiveEventSource = {
  close: () => void;
};

/** Exponentielles Backoff mit Jitter, max 30s (testbar). */
export function computeReconnectDelayMs(attempt: number): number {
  const base = 400;
  const cap = 30_000;
  const step = Math.min(attempt, 10);
  const exp = Math.min(cap, base * 2 ** step);
  const jitter = exp * (0.88 + Math.random() * 0.24);
  return Math.min(cap, Math.round(jitter));
}

function attachEventHandlers(es: EventSource, handlers: LiveSseHandlers): void {
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
  es.addEventListener("ping", () => handlers.onPing?.());
}

/**
 * Startet SSE und verbindet bei Abbruch automatisch neu (Backoff).
 * Schliesst bei unmount/stop explizit mit `close()`.
 */
export function startManagedLiveEventSource(
  options: ManagedLiveEventSourceOptions,
): ManagedLiveEventSource {
  const {
    symbol,
    timeframe,
    handlers,
    onConnectionOpen,
    onReconnectScheduled,
    onConnectionState,
    maxReconnectAttempts = 22,
    onGiveUp,
  } = options;

  let stopped = false;
  let attempt = 0;
  let es: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof globalThis.setTimeout> | null = null;

  const clearReconnectTimer = () => {
    if (reconnectTimer != null) {
      globalThis.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const connect = () => {
    if (stopped) return;
    clearReconnectTimer();
    es?.close();
    es = null;
    onConnectionState?.("connecting");
    const url = buildLiveStreamUrl(symbol, timeframe);
    const source = new EventSource(url.toString());
    es = source;
    attachEventHandlers(source, handlers);

    source.onopen = () => {
      attempt = 0;
      onConnectionState?.("open");
      onConnectionOpen?.();
    };

    source.onerror = () => {
      handlers.onError?.();
      try {
        source.close();
      } catch {
        /* ignore */
      }
      if (es === source) {
        es = null;
      }
      if (stopped) return;
      attempt += 1;
      if (attempt > maxReconnectAttempts) {
        onGiveUp?.({ lastAttempt: attempt });
        onConnectionState?.("given_up");
        return;
      }
      const delayMs = computeReconnectDelayMs(attempt);
      onReconnectScheduled?.({ attempt, delayMs });
      onConnectionState?.("reconnecting");
      clearReconnectTimer();
      reconnectTimer = globalThis.setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, delayMs);
    };
  };

  connect();

  return {
    close: () => {
      stopped = true;
      clearReconnectTimer();
      try {
        es?.close();
      } catch {
        /* ignore */
      }
      es = null;
    },
  };
}
