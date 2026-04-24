/**
 * Live-Terminal SSE: Reconnect mit Backoff, Heartbeat-Timeout, Tab-sicherer BFF-Abort.
 * Nach jeder erfolgreichen Verbindung Callback fuer REST-Backfill (Luecken schliessen).
 */

import { useSyncExternalStore } from "react";

import type { LiveSseHandlers } from "@/lib/sse";
import { buildLiveStreamUrl } from "@/lib/sse";

/** Intern: kompatibel mit bisherigem Live-Terminal. */
export type LiveStreamConnectionState =
  | "connecting"
  | "open"
  | "reconnecting"
  /** User/Unmount: keine weiteren Events. */
  | "disconnected"
  | "given_up";

/**
 * UI- und Audit-Labels (Prompt 56): gleichnamiger Zustand fuer Konsolen-Leiste.
 */
export type LiveSsePublicStatus =
  | "CONNECTING"
  | "CONNECTED"
  | "DISCONNECTED"
  | "RECONNECTING"
  | "GAVE_UP";

export const LIVE_SSE_PING_STALE_MS = 15_000;
export const LIVE_SSE_BACKOFF_MAX_MS = 30_000;
const HEART_CHECK_INTERVAL_MS = 1_000;

let _publicSseStatus: LiveSsePublicStatus = "DISCONNECTED";
const _publicSseSubscribers = new Set<() => void>();

function setGlobalLiveSseStatus(next: LiveSsePublicStatus): void {
  if (_publicSseStatus === next) return;
  _publicSseStatus = next;
  for (const fn of _publicSseSubscribers) {
    fn();
  }
}

function mapToPublic(
  s: LiveStreamConnectionState,
): LiveSsePublicStatus {
  switch (s) {
    case "connecting":
      return "CONNECTING";
    case "open":
      return "CONNECTED";
    case "reconnecting":
      return "RECONNECTING";
    case "disconnected":
      return "DISCONNECTED";
    case "given_up":
      return "GAVE_UP";
    default:
      return "DISCONNECTED";
  }
}

export function getLiveSseGlobalStatus(): LiveSsePublicStatus {
  return _publicSseStatus;
}

export function subscribeGlobalLiveSseStatus(onChange: () => void): () => void {
  _publicSseSubscribers.add(onChange);
  return () => {
    _publicSseSubscribers.delete(onChange);
  };
}

/**
 * Reagiert auf globale Live-SSE-Verbindung (eine pro aktivem Terminal).
 * Wenn kein `startManagedLiveEventSource` laeuft: `DISCONNECTED`.
 */
export function useLiveSseConnectionStatus(): LiveSsePublicStatus {
  return useSyncExternalStore(
    subscribeGlobalLiveSseStatus,
    getLiveSseGlobalStatus,
    getLiveSseGlobalStatus,
  );
}

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
  /** Wartezeit nach ping-Ausbleiben, ms (Default 15_000). */
  pingStaleMs?: number;
};

export type ManagedLiveEventSource = {
  close: () => void;
};

/**
 * Reconnect-Backoff: Start 1s, Verdopplung bis max 30s, leichter Jitter.
 */
export function computeReconnectDelayMs(attempt: number): number {
  const a = Math.max(1, Math.floor(attempt));
  const raw = Math.min(
    LIVE_SSE_BACKOFF_MAX_MS,
    1000 * 2 ** (a - 1),
  );
  const jitter = raw * (0.9 + Math.random() * 0.2);
  return Math.min(LIVE_SSE_BACKOFF_MAX_MS, Math.round(jitter));
}

function wrapHandlers(
  h: LiveSseHandlers,
  onPing: () => void,
): LiveSseHandlers {
  return {
    ...h,
    onPing: () => {
      onPing();
      h.onPing?.();
    },
  };
}

function attachEventHandlers(
  es: EventSource,
  handlers: LiveSseHandlers,
): void {
  const wrap =
    (fn?: (data: unknown) => void) => (ev: MessageEvent<string>) => {
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
  es.addEventListener("ping", () => {
    handlers.onPing?.();
  });
}

/**
 * Startet SSE und verbindet bei Abbruch automatisch neu (Backoff + Ping-Timeout).
 * Schliesst bei unmount/stop explizit mit `close()`.
 */
export function startManagedLiveEventSource(
  options: ManagedLiveEventSourceOptions,
): ManagedLiveEventSource {
  const {
    symbol,
    timeframe,
    handlers: rawHandlers,
    onConnectionOpen,
    onReconnectScheduled,
    onConnectionState,
    maxReconnectAttempts = 22,
    onGiveUp,
    pingStaleMs = LIVE_SSE_PING_STALE_MS,
  } = options;

  const emit = (s: LiveStreamConnectionState) => {
    onConnectionState?.(s);
    setGlobalLiveSseStatus(mapToPublic(s));
  };

  let stopped = false;
  let attempt = 0;
  let es: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof globalThis.setTimeout> | null = null;
  let lastPingAt = 0;
  let pingWatchTimer: ReturnType<typeof globalThis.setInterval> | null = null;

  const clearPingWatch = () => {
    if (pingWatchTimer != null) {
      globalThis.clearInterval(pingWatchTimer);
      pingWatchTimer = null;
    }
  };

  const clearReconnectTimer = () => {
    if (reconnectTimer != null) {
      globalThis.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const notePing = () => {
    lastPingAt = Date.now();
  };

  const onPingInternal = () => {
    notePing();
  };

  const beginReconnect = () => {
    rawHandlers.onError?.();
    clearPingWatch();
    if (stopped) {
      return;
    }
    attempt += 1;
    if (attempt > maxReconnectAttempts) {
      onGiveUp?.({ lastAttempt: attempt });
      emit("given_up");
      return;
    }
    const delayMs = computeReconnectDelayMs(attempt);
    onReconnectScheduled?.({ attempt, delayMs });
    emit("reconnecting");
    clearReconnectTimer();
    reconnectTimer = globalThis.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delayMs);
  };

  const connect = () => {
    if (stopped) {
      return;
    }
    clearReconnectTimer();
    es?.close();
    es = null;
    clearPingWatch();
    emit("connecting");
    const u = buildLiveStreamUrl(symbol, timeframe);
    const source = new EventSource(u.toString());
    es = source;
    const handlers = wrapHandlers(rawHandlers, onPingInternal);
    attachEventHandlers(source, handlers);

    source.onopen = () => {
      attempt = 0;
      notePing();
      clearPingWatch();
      emit("open");
      onConnectionOpen?.();
      pingWatchTimer = globalThis.setInterval(() => {
        if (stopped || es !== source) {
          return;
        }
        if (Date.now() - lastPingAt > pingStaleMs) {
          try {
            source.close();
          } catch {
            /* ignore */
          }
          if (es === source) {
            es = null;
          }
          beginReconnect();
        }
      }, HEART_CHECK_INTERVAL_MS);
    };

    source.onerror = () => {
      if (es !== source) {
        return;
      }
      clearPingWatch();
      if (stopped) {
        return;
      }
      try {
        source.close();
      } catch {
        /* ignore */
      }
      if (es === source) {
        es = null;
      }
      beginReconnect();
    };
  };

  connect();

  return {
    close: () => {
      stopped = true;
      clearReconnectTimer();
      clearPingWatch();
      try {
        es?.close();
      } catch {
        /* ignore */
      }
      es = null;
      emit("disconnected");
    },
  };
}
