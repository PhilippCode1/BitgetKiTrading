import {
  executionPathFromSystemHealth,
  type ExecutionPathViewModel,
} from "@/lib/execution-path-view-model";
import type {
  LiveDataLineageSegment,
  LiveMarketFreshness,
  LiveStateResponse,
  SignalsRecentResponse,
  SystemHealthResponse,
} from "@/lib/types";

/** Primäre Kennzeichnung für die UI (Ampel). */
export type LiveDataPrimaryBadge =
  | "LIVE"
  | "SHADOW"
  | "PAPER"
  | "NO_LIVE"
  | "STALE"
  | "PARTIAL"
  | "DEGRADED_READ"
  | "ERROR"
  | "LOADING";

export type LiveDataSurfaceKind =
  | "market_chart"
  | "terminal"
  | "signals_list"
  | "health_overview"
  | "broker_ops"
  | "market_universe_meta";

export type LiveDataSurfaceModel = Readonly<{
  surfaceKind: LiveDataSurfaceKind;
  primaryBadge: LiveDataPrimaryBadge;
  /** Ausführungsspur (nicht gleich Marktfrische). */
  executionLane: "live" | "shadow" | "paper" | "unknown";
  serverTsMs: number | null;
  /** Letzte bekannte Markt-Einspielung (Ingest), wenn verfügbar */
  lastMarketIngestTsMs: number | null;
  /** Letzte Kerzen-Bar (Start), wenn verfügbar */
  lastCandleBarStartTsMs: number | null;
  marketFreshnessStatus: LiveMarketFreshness["status"] | null;
  lineageTotal: number;
  lineageWithData: number;
  /** segment_id der Lücken */
  missingSegmentIds: readonly string[];
  demoOrFixture: boolean;
  readDegraded: boolean;
  fetchFailed: boolean;
  loading: boolean;
  /** i18n-Key (z. B. live.terminal.streamPoll) oder null */
  streamStabilityKey: string | null;
  streamStabilityVars?: Record<string, string | number | boolean>;
  /** kürzer Schlüssel für Quellzeile */
  dataSourceSummaryKey: "liveStateGateway" | "healthSnapshot" | "signalsApi" | "brokerApi";
  /** Optionale Kontextzeilen (i18n keys mit Parametern, aufgelöst im Client) */
  extraHintKeys: readonly { key: string; vars?: Record<string, string | number> }[];
  /** Für „betroffene Bereiche“ */
  affectedAreaKeys: readonly string[];
}>;

function inferExecutionLane(
  vm: ExecutionPathViewModel | null | undefined,
  executionModeLabel: string | null | undefined,
): LiveDataSurfaceModel["executionLane"] {
  const mode = (
    vm?.execution_mode ??
    executionModeLabel ??
    ""
  ).toLowerCase();
  if (mode.includes("paper")) return "paper";
  if (mode.includes("shadow")) return "shadow";
  if (mode.includes("live")) return "live";
  if (vm?.paper_path_active && !vm?.live_trade_enable) return "paper";
  if (vm?.shadow_path_active || vm?.shadow_trade_enable) return "shadow";
  if (vm?.live_trade_enable) return "live";
  return "unknown";
}

function lineageStats(segments: LiveDataLineageSegment[] | undefined): {
  total: number;
  withData: number;
  missingIds: string[];
} {
  const list = segments ?? [];
  const withData = list.filter((s) => s.has_data).length;
  return {
    total: list.length,
    withData,
    missingIds: list.filter((s) => !s.has_data).map((s) => s.segment_id),
  };
}

function pickPrimaryBadge(args: {
  fetchFailed: boolean;
  loading: boolean;
  readDegraded: boolean;
  mf: LiveMarketFreshness | null;
  candleCount: number;
  lineageWithData: number;
  lineageTotal: number;
  demoOrFixture: boolean;
}): LiveDataPrimaryBadge {
  if (args.loading) return "LOADING";
  if (args.fetchFailed) return "ERROR";
  if (args.readDegraded) return "DEGRADED_READ";
  if (args.demoOrFixture) return "PARTIAL";
  if (!args.mf) {
    if (args.candleCount === 0) return "NO_LIVE";
    return "PARTIAL";
  }
  if (
    args.mf.status === "stale" ||
    args.mf.status === "dead" ||
    args.mf.status === "no_candles"
  ) {
    if (args.candleCount === 0 && args.mf.status === "no_candles")
      return "NO_LIVE";
    return "STALE";
  }
  if (args.mf.status === "delayed") return "PARTIAL";
  if (
    args.lineageTotal > 0 &&
    args.lineageWithData < args.lineageTotal &&
    args.lineageWithData < Math.max(1, Math.ceil(args.lineageTotal * 0.85))
  ) {
    return "PARTIAL";
  }
  if (args.mf.status === "live") return "LIVE";
  return "PARTIAL";
}

/**
 * Volles Modell aus GET /v1/live/state (Chart, Terminal).
 */
export function buildLiveDataSurfaceModelFromLiveState(input: Readonly<{
  live: LiveStateResponse | null;
  executionVm: ExecutionPathViewModel | null;
  executionModeLabel?: string | null;
  fetchError: boolean;
  loading: boolean;
  candleCount: number;
  surfaceKind: Extract<LiveDataSurfaceKind, "market_chart" | "terminal">;
  streamStabilityKey?: string | null;
  streamStabilityVars?: Record<string, string | number | boolean>;
}>): LiveDataSurfaceModel {
  const live = input.live;
  const mf = live?.market_freshness ?? null;
  const lin = lineageStats(live?.data_lineage);
  const demoOrFixture = Boolean(live?.demo_data_notice?.show_banner);
  const readDegraded = live?.status === "degraded";
  const fetchFailed = input.fetchError;
  const loading = input.loading;

  const primaryBadge = pickPrimaryBadge({
    fetchFailed,
    loading,
    readDegraded,
    mf,
    candleCount: input.candleCount,
    lineageWithData: lin.withData,
    lineageTotal: lin.total,
    demoOrFixture,
  });

  const lane = inferExecutionLane(
    input.executionVm,
    input.executionModeLabel,
  );

  const lastIngest = mf?.candle?.last_ingest_ts_ms ?? null;
  const lastBar = mf?.candle?.last_start_ts_ms ?? null;

  const extra: { key: string; vars?: Record<string, string | number> }[] = [];
  if (demoOrFixture) {
    extra.push({ key: "live.dataSituation.hintDemoFixture" });
  }
  if (readDegraded && live?.message) {
    extra.push({
      key: "live.dataSituation.hintDegradedMessage",
      vars: { msg: String(live.message).slice(0, 200) },
    });
  } else if (readDegraded) {
    extra.push({ key: "live.dataSituation.hintDegradedGeneric" });
  }

  const affected: string[] = [];
  if (primaryBadge === "NO_LIVE" || primaryBadge === "STALE") {
    affected.push("live.dataSituation.areaChart");
    affected.push("live.dataSituation.areaSignals");
  }
  if (lin.missingIds.length > 0) {
    if (lin.missingIds.some((id) => /news/i.test(id)))
      affected.push("live.dataSituation.areaNews");
    if (lin.missingIds.some((id) => /paper|sim/i.test(id)))
      affected.push("live.dataSituation.areaPaper");
  }

  return {
    surfaceKind: input.surfaceKind,
    primaryBadge,
    executionLane: lane,
    serverTsMs: live?.server_ts_ms ?? null,
    lastMarketIngestTsMs: lastIngest,
    lastCandleBarStartTsMs: lastBar,
    marketFreshnessStatus: mf?.status ?? null,
    lineageTotal: lin.total,
    lineageWithData: lin.withData,
    missingSegmentIds: lin.missingIds,
    demoOrFixture,
    readDegraded,
    fetchFailed,
    loading,
    streamStabilityKey: input.streamStabilityKey ?? null,
    streamStabilityVars: input.streamStabilityVars,
    dataSourceSummaryKey: "liveStateGateway",
    extraHintKeys: extra,
    affectedAreaKeys: [...new Set(affected)],
  };
}

/**
 * Kompakte Plattform-Sicht nur aus System-Health (Konsole-Start, wenn kein Symbol-Kontext).
 */
export function buildLiveDataSurfaceModelFromHealth(input: Readonly<{
  health: SystemHealthResponse | null;
  surfaceKind?: Extract<
    LiveDataSurfaceKind,
    "health_overview" | "market_universe_meta"
  >;
}>): LiveDataSurfaceModel | null {
  const h = input.health;
  if (!h) return null;
  const sk = input.surfaceKind ?? "health_overview";
  const vm = {
    source: "system_health" as const,
    execution_mode: h.execution.execution_mode,
    strategy_execution_mode: h.execution.strategy_execution_mode,
    paper_path_active: h.execution.paper_path_active,
    shadow_trade_enable: h.execution.shadow_trade_enable,
    shadow_path_active: h.execution.shadow_path_active,
    live_trade_enable: h.execution.live_trade_enable,
    live_order_submission_enabled: h.execution.live_order_submission_enabled,
    require_shadow_match_before_live: false,
  };
  const lane = inferExecutionLane(vm, h.execution.execution_mode);
  const now = h.server_ts_ms;
  const lc = h.data_freshness.last_candle_ts_ms;
  const ls = h.data_freshness.last_signal_ts_ms;
  const STALE_MS = 5 * 60 * 1000;
  const staleCandle = lc != null && now - lc > STALE_MS;
  const noCandle =
    lc == null &&
    (h.warnings.some((w) => /no_candles|no_candle/i.test(w)) ||
      h.database !== "ok");

  let primary: LiveDataPrimaryBadge = "PARTIAL";
  if (noCandle) primary = "NO_LIVE";
  else if (staleCandle) primary = "STALE";
  else if (lc != null) primary = "LIVE";

  const extra: { key: string; vars?: Record<string, string | number> }[] = [
    {
      key:
        sk === "market_universe_meta"
          ? "live.dataSituation.muMetaLead"
          : "live.dataSituation.healthOverviewLead",
    },
  ];

  return {
    surfaceKind: sk,
    primaryBadge: primary,
    executionLane: lane,
    serverTsMs: h.server_ts_ms,
    lastMarketIngestTsMs: lc,
    lastCandleBarStartTsMs: null,
    marketFreshnessStatus: null,
    lineageTotal: 0,
    lineageWithData: 0,
    missingSegmentIds: [],
    demoOrFixture: false,
    readDegraded: false,
    fetchFailed: false,
    loading: false,
    streamStabilityKey: null,
    streamStabilityVars: undefined,
    dataSourceSummaryKey: "healthSnapshot",
    extraHintKeys: extra,
    affectedAreaKeys:
      primary === "NO_LIVE" || primary === "STALE"
        ? ["live.dataSituation.areaChart", "live.dataSituation.areaSignals"]
        : [],
  };
}

/**
 * Signalliste (GET /v1/signals/recent) — kein Ersatz für Markt-Live-State.
 */
export function buildLiveDataSurfaceModelFromSignalsRead(input: Readonly<{
  data: SignalsRecentResponse;
  executionVm: ExecutionPathViewModel | null;
  fetchFailed: boolean;
}>): LiveDataSurfaceModel {
  const degraded = input.data.status === "degraded";
  const empty = Boolean(input.data.empty_state) || input.data.items.length === 0;
  const lane = inferExecutionLane(input.executionVm, null);

  let primary: LiveDataPrimaryBadge = "LIVE";
  if (input.fetchFailed) primary = "ERROR";
  else if (degraded) primary = "DEGRADED_READ";
  else if (empty) primary = "NO_LIVE";

  const extra: { key: string; vars?: Record<string, string | number> }[] = [
    { key: "live.dataSituation.signalsFeedLead" },
  ];
  if (degraded && input.data.message) {
    extra.push({
      key: "live.dataSituation.hintDegradedMessage",
      vars: { msg: String(input.data.message).slice(0, 200) },
    });
  }
  if (input.data.next_step) {
    extra.push({
      key: "live.dataSituation.signalsNextStep",
      vars: { step: String(input.data.next_step).slice(0, 160) },
    });
  }

  const affected: string[] = ["live.dataSituation.areaSignalTable"];
  if (empty) affected.push("live.dataSituation.areaSignalFilters");

  return {
    surfaceKind: "signals_list",
    primaryBadge: primary,
    executionLane: lane,
    serverTsMs: null,
    lastMarketIngestTsMs: null,
    lastCandleBarStartTsMs: null,
    marketFreshnessStatus: null,
    lineageTotal: 0,
    lineageWithData: 0,
    missingSegmentIds: [],
    demoOrFixture: false,
    readDegraded: degraded,
    fetchFailed: input.fetchFailed,
    loading: false,
    streamStabilityKey: null,
    streamStabilityVars: undefined,
    dataSourceSummaryKey: "signalsApi",
    extraHintKeys: extra,
    affectedAreaKeys: affected,
  };
}

/**
 * Live-Broker-Seite: Runtime + geladene Sektionen (kein Kerzen-Stream).
 */
export function buildLiveDataSurfaceModelFromBrokerPage(input: Readonly<{
  executionVm: ExecutionPathViewModel | null;
  runtimeSnapshotTs: string | null;
  upstreamOk: boolean | null;
  sectionErrorCount: number;
  runtimeFetchFailed: boolean;
}>): LiveDataSurfaceModel {
  const lane = inferExecutionLane(input.executionVm, null);
  const partial = input.sectionErrorCount > 0 || input.upstreamOk === false;
  let primary: LiveDataPrimaryBadge = "LIVE";
  if (input.runtimeFetchFailed) primary = "ERROR";
  else if (partial) primary = "PARTIAL";

  const extra: { key: string; vars?: Record<string, string | number> }[] = [
    {
      key: "live.dataSituation.brokerLead",
      vars: { sections: input.sectionErrorCount },
    },
  ];
  if (input.runtimeSnapshotTs) {
    extra.push({
      key: "live.dataSituation.brokerSnapshotTs",
      vars: { ts: input.runtimeSnapshotTs },
    });
  }

  return {
    surfaceKind: "broker_ops",
    primaryBadge: primary,
    executionLane: lane,
    serverTsMs: null,
    lastMarketIngestTsMs: null,
    lastCandleBarStartTsMs: null,
    marketFreshnessStatus: null,
    lineageTotal: Math.max(1, input.sectionErrorCount + 1),
    lineageWithData: input.sectionErrorCount > 0 ? 1 : Math.max(1, 1),
    missingSegmentIds: [],
    demoOrFixture: false,
    readDegraded: false,
    fetchFailed: input.runtimeFetchFailed,
    loading: false,
    streamStabilityKey: null,
    streamStabilityVars: undefined,
    dataSourceSummaryKey: "brokerApi",
    extraHintKeys: extra,
    affectedAreaKeys:
      input.sectionErrorCount > 0
        ? ["live.dataSituation.areaBrokerPanels"]
        : [],
  };
}

/**
 * Shadow-Live-Seite: Live-State (Kerzen/Lineage) + optionale Health-Spur + Teilfehler
 * bei Decisions/Fills/Paper.
 */
export function buildLiveDataSurfaceModelFromShadowLivePage(input: Readonly<{
  health: SystemHealthResponse | null;
  live: LiveStateResponse | null;
  liveFetchFailed: boolean;
  sectionErrorCount: number;
}>): LiveDataSurfaceModel {
  const vm = executionPathFromSystemHealth(input.health);
  const exLabel = input.health?.execution?.execution_mode ?? null;
  const base = buildLiveDataSurfaceModelFromLiveState({
    live: input.live,
    executionVm: vm,
    executionModeLabel: exLabel,
    fetchError: input.liveFetchFailed,
    loading: false,
    candleCount: input.live?.candles?.length ?? 0,
    surfaceKind: "market_chart",
  });

  if (input.sectionErrorCount === 0) {
    return base;
  }

  const extra = [
    ...base.extraHintKeys,
    {
      key: "live.dataSituation.shadowPartialSections",
      vars: { n: input.sectionErrorCount },
    },
  ];

  const affected = new Set<string>([...base.affectedAreaKeys]);
  affected.add("live.dataSituation.areaShadowPanels");

  let primary = base.primaryBadge;
  if (primary === "LIVE") {
    primary = "PARTIAL";
  } else if (primary === "LOADING") {
    primary = "PARTIAL";
  }

  return {
    ...base,
    primaryBadge: primary,
    extraHintKeys: extra,
    affectedAreaKeys: [...affected],
  };
}
