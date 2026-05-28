/**
 * Browser-sicherer Dashboard-API-Client: nur same-origin BFF (`/api/dashboard/gateway/v1/...`).
 * Kein server-only, keine Gateway-Secrets, kein direkter Upstream vom Client.
 */

import {
  apiFetchErrorConfig,
  apiFetchErrorFromHttp,
  apiFetchErrorNetwork,
  apiFetchErrorParse,
  extractErrorDetailFromBody,
  isApiFetchError,
} from "@/lib/api-fetch-errors";

export { ApiFetchError, isApiFetchError } from "@/lib/api-fetch-errors";
export type { ApiFetchKind } from "@/lib/api-fetch-errors";

import { DASHBOARD_GATEWAY_CLIENT_FAILURE } from "@/lib/dashboard-client-gateway-events";
import { isRetryableGatewayGetStatus } from "@/lib/gateway-get-retry-policy";
import { classifyFetchError } from "@/lib/user-facing-fetch-error";
import type {
  LiveBrokerOrdersResponse,
  LiveStateResponse,
  MarketUniverseCandlesResponse,
  PaperOpenResponse,
  SystemHealthResponse,
} from "@/lib/types";

const BROWSER_ATTEMPT_TIMEOUT_MS = 22_000;
const BFF_CACHE_FRESH_MS = 5_000;
const BFF_CACHE_STALE_MS = 90_000;
const BFF_RETRY_BACKOFF_MS = [220, 600] as const;

type BffCacheEntry = { data: unknown; freshUntil: number; staleUntil: number };
const _bffCache = new Map<string, BffCacheEntry>();
const _bffInflight = new Map<string, Promise<unknown>>();

function _sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function _warnIfGatewayReadDegraded(
  path: string,
  bffPath: string | undefined,
  data: unknown,
): void {
  if (!data || typeof data !== "object" || Array.isArray(data)) return;
  const o = data as Record<string, unknown>;
  if (o.status !== "degraded") return;
  console.warn("[dashboard-api-client] gateway read degraded (HTTP ok)", {
    path,
    bffPath,
    degradation_reason:
      typeof o.degradation_reason === "string" ? o.degradation_reason : null,
    message: typeof o.message === "string" ? o.message.slice(0, 240) : null,
  });
}

function _isTransientBrowserFetchError(e: unknown): boolean {
  if (!(e instanceof Error)) return false;
  const m = e.message.toLowerCase();
  return (
    m.includes("fetch failed") ||
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("econnrefused") ||
    m.includes("econnreset") ||
    m.includes("etimedout") ||
    m.includes("aborted")
  );
}

function notifyBrowserGatewayReadFailure(err: unknown): void {
  if (typeof window === "undefined" || !isApiFetchError(err)) return;
  const kind = classifyFetchError(err);
  window.dispatchEvent(
    new CustomEvent(DASHBOARD_GATEWAY_CLIENT_FAILURE, {
      detail: {
        kind,
        code: err.code ?? null,
        path: err.path,
      },
    }),
  );
}

async function getJsonViaDashboardBffExecute<T>(
  fullUrl: string,
  path: string,
  bffPath: string,
): Promise<T> {
  const maxAttempts = 3;
  let lastErr: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(fullUrl, {
        cache: "no-store",
        signal: AbortSignal.timeout(BROWSER_ATTEMPT_TIMEOUT_MS),
      });
      const text = await res.text();
      if (res.ok) {
        let parsed: T;
        try {
          parsed = JSON.parse(text) as T;
        } catch (e) {
          const pErr = apiFetchErrorParse(path, bffPath);
          notifyBrowserGatewayReadFailure(pErr);
          throw pErr;
        }
        _warnIfGatewayReadDegraded(path, bffPath, parsed);
        return parsed;
      }
      if (
        isRetryableGatewayGetStatus(res.status) &&
        attempt < maxAttempts - 1
      ) {
        await _sleep(BFF_RETRY_BACKOFF_MS[attempt] ?? 900);
        continue;
      }
      const httpErr = apiFetchErrorFromHttp({
        path,
        bffPath,
        status: res.status,
        bodyText: text,
      });
      notifyBrowserGatewayReadFailure(httpErr);
      throw httpErr;
    } catch (e) {
      if (isApiFetchError(e)) throw e;
      lastErr = e;
      if (attempt < maxAttempts - 1 && _isTransientBrowserFetchError(e)) {
        await _sleep(BFF_RETRY_BACKOFF_MS[attempt] ?? 900);
        continue;
      }
      const nErr = apiFetchErrorNetwork(path, e, bffPath);
      notifyBrowserGatewayReadFailure(nErr);
      throw nErr;
    }
  }
  const lastNet = apiFetchErrorNetwork(path, lastErr, bffPath);
  notifyBrowserGatewayReadFailure(lastNet);
  throw lastNet;
}

async function getJsonViaDashboardBff<T>(
  bffPath: string,
  path: string,
): Promise<T> {
  const u = new URL(bffPath, window.location.origin);
  const fullUrl = u.toString();
  const now = Date.now();

  const cached = _bffCache.get(bffPath);
  if (cached && cached.freshUntil > now) {
    return cached.data as T;
  }

  const inflight = _bffInflight.get(bffPath) as Promise<T> | undefined;
  if (inflight) return inflight;

  if (cached && cached.staleUntil > now && cached.freshUntil <= now) {
    void getJsonViaDashboardBffExecute<T>(fullUrl, path, bffPath)
      .then((data) => {
        _bffCache.set(bffPath, {
          data,
          freshUntil: Date.now() + BFF_CACHE_FRESH_MS,
          staleUntil: Date.now() + BFF_CACHE_STALE_MS,
        });
      })
      .catch(() => undefined);
    return cached.data as T;
  }

  const task = getJsonViaDashboardBffExecute<T>(fullUrl, path, bffPath)
    .then((data) => {
      _bffCache.set(bffPath, {
        data,
        freshUntil: Date.now() + BFF_CACHE_FRESH_MS,
        staleUntil: Date.now() + BFF_CACHE_STALE_MS,
      });
      return data;
    })
    .finally(() => {
      _bffInflight.delete(bffPath);
    });
  _bffInflight.set(bffPath, task);
  return task;
}

/** GET ueber Dashboard-BFF — nur im Browser aufrufen. */
export async function getJsonBrowser<T>(
  path: string,
  qs?: Record<string, string | number | undefined | null>,
): Promise<T> {
  if (typeof window === "undefined") {
    throw apiFetchErrorConfig(
      path,
      "getJsonBrowser ist nur im Browser erlaubt — Server nutzt @/lib/api.",
    );
  }
  const rel = path.startsWith("/") ? path.slice(1) : path;
  if (!rel.startsWith("v1/")) {
    throw apiFetchErrorConfig(
      path,
      `GET ${path}: Erwarteter Pfad unter /v1/* fuer Gateway-BFF.`,
    );
  }
  const u = new URL(`/api/dashboard/gateway/${rel}`, window.location.origin);
  if (qs) {
    for (const [k, v] of Object.entries(qs)) {
      if (v === undefined || v === null || v === "") continue;
      u.searchParams.set(k, String(v));
    }
  }
  return getJsonViaDashboardBff<T>(u.pathname + u.search, path);
}

export async function fetchLiveState(params: {
  symbol: string;
  timeframe: string;
  limit?: number;
}): Promise<LiveStateResponse> {
  return getJsonBrowser<LiveStateResponse>("/v1/live/state", {
    symbol: params.symbol,
    timeframe: params.timeframe,
    limit: params.limit,
  });
}

export async function fetchMarketUniverseCandles(params: {
  symbol: string;
  timeframe: string;
  limit?: number;
}): Promise<MarketUniverseCandlesResponse> {
  return getJsonBrowser<MarketUniverseCandlesResponse>(
    "/v1/market-universe/candles",
    {
      symbol: params.symbol,
      timeframe: params.timeframe,
      limit: params.limit ?? 500,
    },
  );
}

export async function fetchPaperOpen(
  symbol?: string,
): Promise<PaperOpenResponse> {
  return getJsonBrowser<PaperOpenResponse>("/v1/paper/positions/open", {
    symbol,
  });
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  return getJsonBrowser<SystemHealthResponse>("/v1/system/health");
}

export async function fetchLiveBrokerOrders(): Promise<LiveBrokerOrdersResponse> {
  return getJsonBrowser<LiveBrokerOrdersResponse>(
    "/v1/live-broker/orders/recent",
  );
}
