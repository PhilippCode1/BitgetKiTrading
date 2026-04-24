import { cache } from "react";

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
import {
  blockedV1MessageForPath,
  getGatewayBootstrapProbeForRequest,
} from "@/lib/gateway-bootstrap-probe";
import {
  getGatewayFetchErrorInfo,
  type GatewayFetchErrorInfo,
} from "@/lib/gateway-fetch-errors";

export type { GatewayFetchErrorInfo };

import { serverEnv } from "@/lib/server-env";
import { classifyFetchError } from "@/lib/user-facing-fetch-error";
import {
  fetchGatewayGetWithRetry,
  isRetryableGatewayGetStatus,
} from "@/lib/gateway-upstream-fetch";
import type {
  AdminConsoleOverviewResponse,
  AdminPerformanceOverviewResponse,
  AdminTelegramCustomerDeliveryResponse,
  CommerceCustomerPerformanceResponse,
  AdminLlmGovernanceResponse,
  AdminRulesResponse,
  AlertOutboxResponse,
  BacktestsRunsListResponse,
  LearningDriftOnlineStateResponse,
  LearningDriftRecentResponse,
  LearningModelRegistryV2ListResponse,
  LearningPatternsTopResponse,
  LearningRecommendationsListResponse,
  LearningStrategyMetricsListResponse,
  LiveBrokerAuditResponse,
  LiveBrokerForensicTimelineResponse,
  LiveBrokerDecisionsResponse,
  LiveBrokerFillsResponse,
  LiveBrokerKillSwitchResponse,
  LiveBrokerOrderActionsResponse,
  LiveBrokerOrdersResponse,
  LiveBrokerRuntimeResponse,
  LiveStateResponse,
  MonitorAlertsResponse,
  MarketUniverseCandlesResponse,
  MarketUniverseStatusResponse,
  NewsDetail,
  NewsScoredResponse,
  PaperJournalResponse,
  PaperLedgerResponse,
  PaperMetricsResponse,
  PaperOpenResponse,
  PaperTradesResponse,
  SignalDetail,
  SignalExplainResponse,
  SignalsFacetsResponse,
  SignalsRecentResponse,
  StrategiesListResponse,
  StrategyDetailResponse,
  SystemHealthResponse,
} from "@/lib/types";

const SSR_FETCH_MS = 60_000;
/** Pro Browser-Versuch (BFF); bis zu 3 Versuche bei transienten Fehlern. */
const BROWSER_ATTEMPT_TIMEOUT_MS = 22_000;
const BFF_CACHE_FRESH_MS = 5_000;
const BFF_CACHE_STALE_MS = 90_000;
const BFF_RETRY_BACKOFF_MS = [220, 600] as const;

/**
 * API-Client: SSR spricht das Gateway serverseitig an; im Browser laufen Leser
 * ausschliesslich über den BFF-Pfad `/api/dashboard/gateway/v1/...`. Nicht-OK-HTTP
 * → {@link apiFetchErrorFromHttp} inkl. Gateway-Code-Heuristik (`gateway-error-codes.ts`);
 * im Browser zusätzlich {@link notifyBrowserGatewayReadFailure} für die Incident-Zeile.
 */
const _serverGetInflight = new Map<string, Promise<unknown>>();

type BffCacheEntry = { data: unknown; freshUntil: number; staleUntil: number };
const _bffCache = new Map<string, BffCacheEntry>();
const _bffInflight = new Map<string, Promise<unknown>>();

function _sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** HTTP 200 + Leser-Envelope `degraded` ist kein harter Fehler — explizit loggen. */
function _warnIfGatewayReadDegraded(
  path: string,
  bffPath: string | undefined,
  data: unknown,
): void {
  if (!data || typeof data !== "object" || Array.isArray(data)) return;
  const o = data as Record<string, unknown>;
  if (o.status !== "degraded") return;
  console.warn("[dashboard-api] gateway read degraded (HTTP ok)", {
    path,
    bffPath,
    degradation_reason:
      typeof o.degradation_reason === "string" ? o.degradation_reason : null,
    message: typeof o.message === "string" ? o.message.slice(0, 240) : null,
    read_envelope_contract_version:
      typeof o.read_envelope_contract_version === "number"
        ? o.read_envelope_contract_version
        : null,
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

/**
 * BFF-GET im Browser: klassifiziert {@link ApiFetchError} inkl. Gateway-JSON-Codes
 * und feuert ein Event, damit die Shell (Kunden-Portal) einen Incident-Banner zeigen kann.
 */
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

function _qsToSearchParams(
  qs?: Record<string, string | number | undefined | null>,
): URLSearchParams {
  const sp = new URLSearchParams();
  if (!qs) return sp;
  for (const [k, v] of Object.entries(qs)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  return sp;
}

async function getJsonServer<T>(
  path: string,
  qs?: Record<string, string | number | undefined | null>,
): Promise<T> {
  const probe = await getGatewayBootstrapProbeForRequest();
  if (probe.blocksV1Reads) {
    throw apiFetchErrorConfig(path, blockedV1MessageForPath(path, probe));
  }
  const auth = serverEnv.gatewayAuthorizationHeader || "";
  const sp = _qsToSearchParams(qs);
  let res: Response;
  try {
    res = await fetchGatewayGetWithRetry(path, auth, {
      searchParams: sp,
      timeoutMs: SSR_FETCH_MS,
    });
  } catch (e) {
    console.error("[dashboard-api] gateway GET failed", {
      path,
      error: e instanceof Error ? e.message : e,
    });
    throw apiFetchErrorNetwork(path, e);
  }

  const text = await res.text();
  if (!res.ok) {
    console.error("[dashboard-api] upstream HTTP error", {
      path,
      status: res.status,
      detail: extractErrorDetailFromBody(text).slice(0, 400),
    });
    throw apiFetchErrorFromHttp({ path, status: res.status, bodyText: text });
  }
  let parsed: T;
  try {
    parsed = JSON.parse(text) as T;
  } catch (e) {
    console.error("[dashboard-api] JSON parse failed", {
      path,
      snippet: text.slice(0, 240),
      error: e instanceof Error ? e.message : e,
    });
    throw apiFetchErrorParse(path);
  }
  _warnIfGatewayReadDegraded(path, undefined, parsed);
  return parsed;
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
          console.error("[dashboard-api] BFF JSON parse failed", {
            bffPath,
            snippet: text.slice(0, 240),
            error: e instanceof Error ? e.message : e,
          });
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
      console.error("[dashboard-api] BFF HTTP error", {
        bffPath,
        status: res.status,
        detail: extractErrorDetailFromBody(text).slice(0, 400),
      });
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
      console.error("[dashboard-api] BFF fetch failed", { bffPath, error: e });
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
      .catch((err) => {
        if (typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("dashboard-bff-background-revalidate-failed", {
              detail: {
                bffPath,
                message: err instanceof Error ? err.message : String(err),
              },
            }),
          );
        }
      });
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

async function getJson<T>(
  path: string,
  qs?: Record<string, string | number | undefined | null>,
): Promise<T> {
  const isServer = typeof window === "undefined";
  /**
   * Browser: ausschliesslich same-origin BFF — kein direktes Gateway (kein JWT/CORS im Client).
   */
  if (!isServer) {
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

  const key = `${path}?${JSON.stringify(qs ?? {})}`;
  const existing = _serverGetInflight.get(key) as Promise<T> | undefined;
  if (existing) return existing;

  const task = getJsonServer<T>(path, qs).finally(() => {
    _serverGetInflight.delete(key);
  });
  _serverGetInflight.set(key, task);
  return task;
}

export async function fetchLiveState(params: {
  symbol: string;
  timeframe: string;
  limit?: number;
}): Promise<LiveStateResponse> {
  return getJson<LiveStateResponse>("/v1/live/state", {
    symbol: params.symbol,
    timeframe: params.timeframe,
    limit: params.limit,
  });
}

/** Letzte N Kerzen aus tsdb; `symbol` setzt der Client (kein versteckter BTC-Default in dieser Route). */
export async function fetchMarketUniverseCandles(params: {
  symbol: string;
  timeframe: string;
  limit?: number;
}): Promise<MarketUniverseCandlesResponse> {
  return getJson<MarketUniverseCandlesResponse>("/v1/market-universe/candles", {
    symbol: params.symbol,
    timeframe: params.timeframe,
    limit: params.limit ?? 500,
  });
}

export async function fetchSignalsRecent(params: {
  symbol?: string;
  timeframe?: string;
  direction?: string;
  min_strength?: number;
  market_family?: string;
  playbook_id?: string;
  playbook_family?: string;
  trade_action?: string;
  meta_trade_lane?: string;
  regime_state?: string;
  specialist_router_id?: string;
  exit_family?: string;
  decision_state?: string;
  strategy_name?: string;
  signal_class?: string;
  /** Abgestimmt mit Registry: playbook_id ODER strategy_name gleich diesem Wert. */
  signal_registry_key?: string;
  limit?: number;
}): Promise<SignalsRecentResponse> {
  return getJson<SignalsRecentResponse>("/v1/signals/recent", {
    symbol: params.symbol,
    timeframe: params.timeframe,
    direction: params.direction,
    min_strength: params.min_strength,
    market_family: params.market_family,
    playbook_id: params.playbook_id,
    playbook_family: params.playbook_family,
    trade_action: params.trade_action,
    meta_trade_lane: params.meta_trade_lane,
    regime_state: params.regime_state,
    specialist_router_id: params.specialist_router_id,
    exit_family: params.exit_family,
    decision_state: params.decision_state,
    strategy_name: params.strategy_name,
    signal_class: params.signal_class,
    signal_registry_key: params.signal_registry_key,
    limit: params.limit,
  });
}

export async function fetchSignalsFacets(params?: {
  lookback_rows?: number;
}): Promise<SignalsFacetsResponse> {
  return getJson<SignalsFacetsResponse>("/v1/signals/facets", {
    lookback_rows: params?.lookback_rows,
  });
}

export async function fetchSignalDetail(
  signalId: string,
): Promise<SignalDetail> {
  return getJson<SignalDetail>(`/v1/signals/${signalId}`);
}

export async function fetchSignalExplain(
  signalId: string,
): Promise<SignalExplainResponse> {
  return getJson<SignalExplainResponse>(`/v1/signals/${signalId}/explain`);
}

export async function fetchPaperOpen(
  symbol?: string,
): Promise<PaperOpenResponse> {
  return getJson<PaperOpenResponse>("/v1/paper/positions/open", { symbol });
}

export async function fetchPaperTradesRecent(params: {
  symbol?: string;
  limit?: number;
}): Promise<PaperTradesResponse> {
  return getJson<PaperTradesResponse>("/v1/paper/trades/recent", params);
}

export async function fetchPaperMetricsSummary(): Promise<PaperMetricsResponse> {
  return getJson<PaperMetricsResponse>("/v1/paper/metrics/summary");
}

export async function fetchPaperLedgerRecent(params?: {
  limit?: number;
  account_id?: string;
}): Promise<PaperLedgerResponse> {
  return getJson<PaperLedgerResponse>("/v1/paper/ledger/recent", params);
}

export async function fetchPaperJournalRecent(params?: {
  symbol?: string;
  limit?: number;
  account_id?: string;
}): Promise<PaperJournalResponse> {
  return getJson<PaperJournalResponse>("/v1/paper/journal/recent", params);
}

export async function fetchNewsScored(params: {
  min_score?: number;
  sentiment?: string;
  limit?: number;
}): Promise<NewsScoredResponse> {
  return getJson<NewsScoredResponse>("/v1/news/scored", params);
}

export async function fetchNewsDetail(newsId: string): Promise<NewsDetail> {
  return getJson<NewsDetail>(`/v1/news/${newsId}`);
}

export async function fetchStrategies(): Promise<StrategiesListResponse> {
  return getJson<StrategiesListResponse>("/v1/registry/strategies");
}

export async function fetchStrategyDetail(
  id: string,
): Promise<StrategyDetailResponse> {
  return getJson<StrategyDetailResponse>(`/v1/registry/strategies/${id}`);
}

export async function fetchLearningStrategyMetrics(): Promise<LearningStrategyMetricsListResponse> {
  return getJson<LearningStrategyMetricsListResponse>(
    "/v1/learning/metrics/strategies",
  );
}

export async function fetchModelRegistryV2(): Promise<LearningModelRegistryV2ListResponse> {
  return getJson<LearningModelRegistryV2ListResponse>(
    "/v1/learning/models/registry-v2",
  );
}

export async function fetchLearningPatternsTop(): Promise<LearningPatternsTopResponse> {
  return getJson<LearningPatternsTopResponse>("/v1/learning/patterns/top");
}

export async function fetchLearningRecommendations(): Promise<LearningRecommendationsListResponse> {
  return getJson<LearningRecommendationsListResponse>(
    "/v1/learning/recommendations/recent",
  );
}

export async function fetchLearningDrift(): Promise<LearningDriftRecentResponse> {
  return getJson<LearningDriftRecentResponse>("/v1/learning/drift/recent");
}

export async function fetchLearningDriftOnlineState(): Promise<LearningDriftOnlineStateResponse> {
  return getJson<LearningDriftOnlineStateResponse>(
    "/v1/learning/drift/online-state",
  );
}

export async function fetchLearningModelOpsReport(params?: {
  slice_hours?: number;
}): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>("/v1/learning/model-ops/report", {
    slice_hours: params?.slice_hours,
  });
}

export async function fetchBacktestRuns(): Promise<BacktestsRunsListResponse> {
  return getJson<BacktestsRunsListResponse>("/v1/backtests/runs");
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  return getJson<SystemHealthResponse>("/v1/system/health");
}

/** Eine Instanz pro Request — vermeidet parallele doppelte /v1/system/health-Aufrufe im Layout + Seiten. */
export const fetchSystemHealthCached = cache(fetchSystemHealth);

/**
 * Health für Statusleisten: kein stilles Verschlucken — Fehler explizit an die UI zurückgeben.
 */
export async function fetchSystemHealthBestEffort(): Promise<{
  health: SystemHealthResponse | null;
  error: GatewayFetchErrorInfo | null;
}> {
  try {
    const health = await fetchSystemHealthCached();
    return { health, error: null };
  } catch (e) {
    return { health: null, error: getGatewayFetchErrorInfo(e) };
  }
}

export async function fetchMarketUniverseStatus(): Promise<MarketUniverseStatusResponse> {
  return getJson<MarketUniverseStatusResponse>("/v1/market-universe/status");
}

export async function fetchMonitorAlertsOpen(): Promise<MonitorAlertsResponse> {
  return getJson<MonitorAlertsResponse>("/v1/monitor/alerts/open");
}

/** Prompt 74: ops.self_healing_state via Gateway. */
export type SelfHealingStatusItem = {
  service_name: string;
  health_phase: string;
  updated_ts: number | null;
  restart_events_ts: number[];
  timeline: Array<{
    ts_ms: number;
    event: string;
    message?: string;
    details?: Record<string, unknown>;
  }>;
};

export type SelfHealingStatusResponse = {
  ok: boolean;
  items: SelfHealingStatusItem[];
  empty?: boolean;
  degradation_reason?: string;
};

export async function fetchSelfHealingStatus(): Promise<SelfHealingStatusResponse> {
  return getJson<SelfHealingStatusResponse>("/v1/ops/self-healing/status");
}

export async function fetchAlertOutboxRecent(): Promise<AlertOutboxResponse> {
  return getJson<AlertOutboxResponse>("/v1/alerts/outbox/recent");
}

export async function fetchAdminRules(): Promise<AdminRulesResponse> {
  return getJson<AdminRulesResponse>("/v1/admin/rules");
}

export async function fetchAdminConsoleOverview(): Promise<AdminConsoleOverviewResponse> {
  return getJson<AdminConsoleOverviewResponse>("/v1/admin/console-overview");
}

export async function fetchAdminTelegramCustomerDelivery(): Promise<AdminTelegramCustomerDeliveryResponse> {
  return getJson<AdminTelegramCustomerDeliveryResponse>(
    "/v1/admin/telegram-customer-delivery",
  );
}

export async function fetchCommerceCustomerPerformance(params?: {
  trades_limit?: number;
  symbol?: string;
}): Promise<CommerceCustomerPerformanceResponse> {
  return getJson<CommerceCustomerPerformanceResponse>(
    "/v1/commerce/customer/performance",
    {
      trades_limit: params?.trades_limit,
      symbol: params?.symbol,
    },
  );
}

export async function fetchAdminPerformanceOverview(): Promise<AdminPerformanceOverviewResponse> {
  return getJson<AdminPerformanceOverviewResponse>(
    "/v1/admin/performance-overview",
  );
}

export async function fetchCommerceAdminSubscriptions(params?: {
  limit?: number;
}): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/admin/billing/subscriptions",
    {
      limit: params?.limit,
    },
  );
}

export async function fetchCommerceAdminContractReviewQueue(params?: {
  status?: string;
}): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/admin/contracts/review-queue",
    {
      status: params?.status,
    },
  );
}

export async function fetchCommerceAdminProfitFeeStatements(params?: {
  limit?: number;
  tenant_id?: string;
  status?: string;
}): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/admin/profit-fee/statements",
    {
      limit: params?.limit,
      tenant_id: params?.tenant_id,
      status: params?.status,
    },
  );
}

export async function fetchCommerceAdminPaymentsDiagnostics(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/admin/payments/diagnostics",
  );
}

export async function fetchCommerceAdminBillingSnapshot(
  tenantId: string,
): Promise<Record<string, unknown>> {
  const enc = encodeURIComponent(tenantId);
  return getJson<Record<string, unknown>>(
    `/v1/commerce/admin/billing/tenant/${enc}/snapshot`,
  );
}

export async function fetchAdminLlmGovernance(): Promise<AdminLlmGovernanceResponse> {
  return getJson<AdminLlmGovernanceResponse>("/v1/admin/llm-governance");
}

export async function fetchLiveBrokerRuntime(): Promise<LiveBrokerRuntimeResponse> {
  return getJson<LiveBrokerRuntimeResponse>("/v1/live-broker/runtime");
}

export async function fetchLiveBrokerDecisions(): Promise<LiveBrokerDecisionsResponse> {
  return getJson<LiveBrokerDecisionsResponse>(
    "/v1/live-broker/decisions/recent",
  );
}

export async function fetchLiveBrokerOrders(): Promise<LiveBrokerOrdersResponse> {
  return getJson<LiveBrokerOrdersResponse>("/v1/live-broker/orders/recent");
}

export async function fetchLiveBrokerFills(): Promise<LiveBrokerFillsResponse> {
  return getJson<LiveBrokerFillsResponse>("/v1/live-broker/fills/recent");
}

export async function fetchLiveBrokerOrderActions(): Promise<LiveBrokerOrderActionsResponse> {
  return getJson<LiveBrokerOrderActionsResponse>(
    "/v1/live-broker/orders/actions/recent",
  );
}

export async function fetchLiveBrokerKillSwitchActive(): Promise<LiveBrokerKillSwitchResponse> {
  return getJson<LiveBrokerKillSwitchResponse>(
    "/v1/live-broker/kill-switch/active",
  );
}

export async function fetchLiveBrokerKillSwitchEvents(): Promise<LiveBrokerKillSwitchResponse> {
  return getJson<LiveBrokerKillSwitchResponse>(
    "/v1/live-broker/kill-switch/events/recent",
  );
}

export async function fetchLiveBrokerAuditRecent(params?: {
  category?: string;
}): Promise<LiveBrokerAuditResponse> {
  return getJson<LiveBrokerAuditResponse>("/v1/live-broker/audit/recent", {
    category: params?.category,
  });
}

export async function fetchLiveBrokerForensicTimeline(
  executionId: string,
): Promise<LiveBrokerForensicTimelineResponse> {
  return getJson<LiveBrokerForensicTimelineResponse>(
    `/v1/live-broker/executions/${executionId}/forensic-timeline`,
  );
}

export type CommerceUsageSummary = Record<string, unknown>;

export async function fetchCommerceUsageSummary(params?: {
  tenant_id?: string;
}): Promise<CommerceUsageSummary> {
  return getJson<CommerceUsageSummary>("/v1/commerce/usage/summary", {
    tenant_id: params?.tenant_id,
  });
}

export type CommerceUsageLedgerResponse = {
  tenant_id: string;
  items: unknown[];
};

export async function fetchCommerceUsageLedger(params?: {
  tenant_id?: string;
  limit?: number;
}): Promise<CommerceUsageLedgerResponse> {
  return getJson<CommerceUsageLedgerResponse>("/v1/commerce/usage/ledger", {
    tenant_id: params?.tenant_id,
    limit: params?.limit,
  });
}

export type CommerceCustomerMe = Record<string, unknown>;

export async function fetchCommerceCustomerMe(): Promise<CommerceCustomerMe> {
  return getJson<CommerceCustomerMe>("/v1/commerce/customer/me");
}

export async function fetchCommerceCustomerBalance(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>("/v1/commerce/customer/balance");
}

export async function fetchCommerceCustomerIntegrations(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>("/v1/commerce/customer/integrations");
}

export async function fetchCommerceCustomerPayments(params?: {
  limit?: number;
}): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>("/v1/commerce/customer/payments", {
    limit: params?.limit,
  });
}

export async function fetchCommerceCustomerHistory(params?: {
  ledger_limit?: number;
  audit_limit?: number;
}): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>("/v1/commerce/customer/history", {
    ledger_limit: params?.ledger_limit,
    audit_limit: params?.audit_limit,
  });
}

export type CommerceContractTemplatesResponse = Record<string, unknown>;
export type CommerceContractsListResponse = Record<string, unknown>;

export async function fetchCommerceContractTemplates(): Promise<CommerceContractTemplatesResponse> {
  return getJson<CommerceContractTemplatesResponse>(
    "/v1/commerce/customer/contracts/templates",
  );
}

export async function fetchCommerceCustomerContracts(): Promise<CommerceContractsListResponse> {
  return getJson<CommerceContractsListResponse>(
    "/v1/commerce/customer/contracts",
  );
}

export async function fetchCommerceBillingPlans(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/customer/billing/plans",
  );
}

export async function fetchCommerceBillingSubscription(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/customer/billing/subscription",
  );
}

export async function fetchCommerceBillingInvoices(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/customer/billing/invoices",
  );
}

export async function fetchCommerceBillingLedger(): Promise<
  Record<string, unknown>
> {
  return getJson<Record<string, unknown>>(
    "/v1/commerce/customer/billing/ledger",
  );
}
