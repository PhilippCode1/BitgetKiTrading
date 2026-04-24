import { gatewayAbsoluteUrl } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";

/** Standard-Timeout fuer idempotente GET- und JSON-Proxys zum API-Gateway. */
export const GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS = 60_000;

/** Kurze Timeouts fuer Commerce- und Admin-Proxys. */
export const GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS = 12_000;

/** HTTP-Status, bei denen ein idempotenter GET nach kurzem Backoff wiederholt werden darf. */
const GET_RETRYABLE_HTTP_STATUS = new Set([408, 429, 502, 503, 504]);

/** Backoff nach Versuch i (ms) — max. drei Versuche insgesamt. */
const GET_RETRY_BACKOFF_MS = [320, 960] as const;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function isTransientNetworkError(e: unknown): boolean {
  if (!(e instanceof Error)) return false;
  const m = e.message.toLowerCase();
  return (
    m.includes("fetch failed") ||
    m.includes("econnrefused") ||
    m.includes("econnreset") ||
    m.includes("etimedout") ||
    m.includes("network") ||
    m.includes("aborted")
  );
}

export function isRetryableGatewayGetStatus(status: number): boolean {
  return GET_RETRYABLE_HTTP_STATUS.has(status);
}

/** Tab-/Client-Abort (BFF) mit optionalem Server-Timeout kombinieren. */
function mergeWithClientAbort(
  base: AbortSignal,
  client: AbortSignal | null | undefined,
): AbortSignal {
  if (client == null) return base;
  const any = (
    AbortSignal as unknown as { any?: (signals: readonly AbortSignal[]) => AbortSignal }
  ).any;
  if (typeof any === "function") {
    return any([base, client]);
  }
  return client;
}

export type FetchGatewayUpstreamInit = Readonly<{
  method?: string;
  searchParams?: URLSearchParams;
  body?: BodyInit | null;
  /** Zusaetzliche Header (Authorization wird immer gesetzt). */
  extraHeaders?: HeadersInit;
  /** Optional: eingehende Request-Header (BFF) — fehlende Trace-IDs werden ergaenzt. */
  traceSource?: Headers | null;
  /**
   * `undefined`: Standard-Timeout (60s).
   * Zahl: explizites Timeout in ms.
   * `null`: kein Timeout-Signal; optional ``abortSignal`` (z. B. Tab-Schliessen BFF, SSE-Longpoll).
   */
  timeoutMs?: number | null;
  /**
   * Z. B. ``Request.signal`` im BFF: Bricht Upstream ab, sobald der Browser-Tab/Client weg ist
   * (verhindert doppelte Gateway-Zombie-Verbindungen).
   */
  abortSignal?: AbortSignal | null;
}>;

/**
 * Einheitlicher Server-zu-Gateway-fetch mit Authorization.
 * Nur in Route Handlers / Server Components verwenden.
 */
export async function fetchGatewayUpstream(
  path: string,
  authorization: string,
  init: FetchGatewayUpstreamInit = {},
): Promise<Response> {
  const url = new URL(gatewayAbsoluteUrl(path));
  if (init.searchParams) {
    init.searchParams.forEach((v, k) => url.searchParams.set(k, v));
  }
  const headers = new Headers(init.extraHeaders);
  applyGatewayTraceHeaders(headers, init.traceSource ?? null);
  headers.set("Authorization", authorization);
  const body = init.body ?? undefined;
  if (body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const reqInit: RequestInit = {
    method: init.method ?? "GET",
    headers,
    body: body === null ? undefined : body,
    cache: "no-store",
  };
  const t = init.timeoutMs;
  const clientAbort = init.abortSignal;
  if (t === undefined) {
    reqInit.signal = mergeWithClientAbort(
      AbortSignal.timeout(GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS),
      clientAbort,
    );
  } else if (t !== null) {
    reqInit.signal = mergeWithClientAbort(AbortSignal.timeout(t), clientAbort);
  } else if (clientAbort) {
    reqInit.signal = clientAbort;
  }
  return fetch(url.toString(), reqInit);
}

/**
 * POST/GET ohne Bearer (selten: z. B. Mock-Webhook mit eigenem Secret-Header).
 */
export async function fetchGatewayWithoutBearer(
  path: string,
  init: FetchGatewayUpstreamInit = {},
): Promise<Response> {
  const url = new URL(gatewayAbsoluteUrl(path));
  if (init.searchParams) {
    init.searchParams.forEach((v, k) => url.searchParams.set(k, v));
  }
  const headers = new Headers(init.extraHeaders);
  applyGatewayTraceHeaders(headers, init.traceSource ?? null);
  const body = init.body ?? undefined;
  if (body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const reqInit: RequestInit = {
    method: init.method ?? "GET",
    headers,
    body: body === null ? undefined : body,
    cache: "no-store",
  };
  const t = init.timeoutMs;
  const clientAbort = init.abortSignal;
  if (t === undefined) {
    reqInit.signal = mergeWithClientAbort(
      AbortSignal.timeout(GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS),
      clientAbort,
    );
  } else if (t !== null) {
    reqInit.signal = mergeWithClientAbort(AbortSignal.timeout(t), clientAbort);
  } else if (clientAbort) {
    reqInit.signal = clientAbort;
  }
  return fetch(url.toString(), reqInit);
}

/**
 * Idempotenter GET mit mehreren Versuchen: transientes Netzwerk + 408/429/502/503/504.
 * Keine Endlosschleife: feste Versuchszahl, kein Retry bei 401/403/404/422.
 */
export async function fetchGatewayGetWithRetry(
  path: string,
  authorization: string,
  options?: Readonly<{ searchParams?: URLSearchParams; timeoutMs?: number }>,
): Promise<Response> {
  const timeoutMs = options?.timeoutMs ?? GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS;
  const maxAttempts = 3;
  let lastError: unknown;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetchGatewayUpstream(path, authorization, {
        searchParams: options?.searchParams,
        timeoutMs,
      });
      if (res.ok) return res;
      if (
        isRetryableGatewayGetStatus(res.status) &&
        attempt < maxAttempts - 1
      ) {
        const wait = GET_RETRY_BACKOFF_MS[attempt] ?? 1200;
        await sleep(wait);
        continue;
      }
      return res;
    } catch (e) {
      lastError = e;
      if (attempt < maxAttempts - 1 && isTransientNetworkError(e)) {
        const wait = GET_RETRY_BACKOFF_MS[attempt] ?? 1200;
        await sleep(wait);
        continue;
      }
      throw e;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}
