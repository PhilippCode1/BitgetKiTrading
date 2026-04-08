import { serverEnv } from "@/lib/server-env";

export type LiveTerminalServerMeta = {
  /** Gateway LIVE_SSE_ENABLED; null wenn Meta nicht lesbar. */
  sseEnabled: boolean | null;
  ssePingSec: number | null;
};

/**
 * Server-only: oeffentliche Gateway-Oberflaeche (kein JWT).
 * Nutzt dieselben Fakten wie `GET /v1/live/stream` (503 wenn SSE aus).
 */
export async function fetchLiveTerminalServerMeta(): Promise<LiveTerminalServerMeta> {
  const base = serverEnv.apiGatewayUrl.replace(/\/$/, "");
  if (!base) {
    return { sseEnabled: null, ssePingSec: null };
  }
  try {
    const ac = new AbortController();
    const to = globalThis.setTimeout(() => ac.abort(), 3500);
    const r = await fetch(`${base}/v1/meta/surface`, {
      signal: ac.signal,
      cache: "no-store",
    });
    globalThis.clearTimeout(to);
    if (!r.ok) {
      return { sseEnabled: null, ssePingSec: null };
    }
    const j = (await r.json()) as Record<string, unknown>;
    const lt = j.live_terminal as Record<string, unknown> | undefined;
    if (!lt || typeof lt !== "object") {
      return { sseEnabled: null, ssePingSec: null };
    }
    return {
      sseEnabled: typeof lt.sse_enabled === "boolean" ? lt.sse_enabled : null,
      ssePingSec: typeof lt.sse_ping_sec === "number" ? lt.sse_ping_sec : null,
    };
  } catch {
    return { sseEnabled: null, ssePingSec: null };
  }
}
