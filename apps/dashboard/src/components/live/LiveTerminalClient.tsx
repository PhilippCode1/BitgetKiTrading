"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ProductMessageCard } from "@/components/product-messages/ProductMessageCard";
import { SurfaceDiagnosticCard } from "@/components/diagnostics/SurfaceDiagnosticCard";
import { EmptyStateHelp } from "@/components/help/EmptyStateHelp";
import { HelpHint } from "@/components/help/HelpHint";
import { useI18n } from "@/components/i18n/I18nProvider";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import { DemoDataNoticeBanner } from "@/components/live/DemoDataNoticeBanner";
import { ChartPanel } from "@/components/live/ChartPanel";
import { LiveDataLineagePanel } from "@/components/live/LiveDataLineagePanel";
import { MicrostructurePanel } from "@/components/live/MicrostructurePanel";
import { NewsPanel } from "@/components/live/NewsPanel";
import { PaperPanel } from "@/components/live/PaperPanel";
import { SignalPanel } from "@/components/live/SignalPanel";
import { StatusPillLink } from "@/components/ui/StatusPillLink";
import { fetchLiveState } from "@/lib/api";
import type { ExecutionPathViewModel } from "@/lib/execution-path-view-model";
import { buildLiveDataSurfaceModelFromLiveState } from "@/lib/live-data-surface-model";
import { consolePath } from "@/lib/console-paths";
import type { LiveStreamConnectionState } from "@/lib/live-event-source";
import { startManagedLiveEventSource } from "@/lib/live-event-source";
import { publicEnv } from "@/lib/env";
import type { LiveTerminalServerMeta } from "@/lib/live-terminal-server-meta";
import { resolveLiveTerminalSurfaceDiagnostic } from "@/lib/surface-diagnostic-catalog";
import { buildProductMessageFromFetchError } from "@/lib/product-messages";
import type {
  LiveCandle,
  LiveMarketFreshness,
  LiveNewsItem,
  LiveSignal,
  LiveStateResponse,
} from "@/lib/types";

const TFS = ["1m", "5m", "15m", "1h", "4h"] as const;

function healthPillVariant(
  h: string | undefined,
): "status-ok" | "status-warn" | "status-bad" {
  if (h === "ok") return "status-ok";
  if (h === "degraded") return "status-warn";
  return "status-bad";
}

function streamPillVariant(
  phase: string,
): "status-ok" | "status-warn" | "status-bad" {
  if (phase === "live") return "status-ok";
  if (phase === "sse_gave_up" || phase === "stale") return "status-bad";
  return "status-warn";
}

function freshnessPillVariant(
  status: LiveMarketFreshness["status"],
): "status-ok" | "status-warn" | "status-bad" | "status-neutral" {
  if (status === "live") return "status-ok";
  if (status === "delayed") return "status-warn";
  if (status === "stale" || status === "dead") return "status-bad";
  return "status-neutral";
}

function freshnessBannerModifier(
  status: LiveMarketFreshness["status"],
):
  | "live-terminal-banner--delayed"
  | "live-terminal-banner--critical"
  | "live-terminal-banner--info" {
  if (status === "delayed") return "live-terminal-banner--delayed";
  if (status === "stale" || status === "dead")
    return "live-terminal-banner--critical";
  return "live-terminal-banner--info";
}

function normTf(x: string): string {
  const u = x.trim();
  if (u.toLowerCase() === "1h") return "1H";
  if (u.toLowerCase() === "4h") return "4H";
  return u;
}

type Props = {
  initial: LiveStateResponse;
  /** SSR: Fehler beim ersten Laden statt stiller Leer-Chart */
  initialLoadError?: string | null;
  symbolOptions: string[];
  /** Server: Gateway `GET /v1/meta/surface` → live_terminal (kein Client-Leak). */
  liveTerminalMeta?: LiveTerminalServerMeta | null;
  /** Aus System-Health — Ausführungsspur für Live-Datenlage */
  executionVm?: ExecutionPathViewModel | null;
};

/** SSE-Payload nur uebernehmen, wenn sie wie ein Signal aussieht — verhindert kaputten React-State. */
function mergeLatestSignal(
  prev: LiveStateResponse["latest_signal"],
  raw: unknown,
): LiveStateResponse["latest_signal"] {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return prev;
  }
  const patch = raw as Record<string, unknown>;
  if (typeof patch.signal_id !== "string" || patch.signal_id.length === 0) {
    return prev;
  }
  const direction =
    typeof patch.direction === "string"
      ? patch.direction
      : (prev?.direction ?? "unknown");
  const strength =
    typeof patch.signal_strength_0_100 === "number"
      ? patch.signal_strength_0_100
      : (prev?.signal_strength_0_100 ?? 0);
  const prob =
    typeof patch.probability_0_1 === "number"
      ? patch.probability_0_1
      : (prev?.probability_0_1 ?? 0);
  return {
    ...(prev && typeof prev === "object" ? prev : {}),
    ...patch,
    signal_id: patch.signal_id,
    direction,
    signal_strength_0_100: strength,
    probability_0_1: prob,
  } as LiveSignal;
}

function freshnessBannerRole(
  status: LiveMarketFreshness["status"],
): "status" | "alert" {
  return status === "stale" || status === "dead" ? "alert" : "status";
}

function mergeCandle(list: LiveCandle[], bar: LiveCandle): LiveCandle[] {
  const next = [...list];
  const i = next.findIndex((c) => c.time_s === bar.time_s);
  if (i >= 0) next[i] = bar;
  else next.push(bar);
  next.sort((a, b) => a.time_s - b.time_s);
  const max = 2000;
  if (next.length > max) return next.slice(-max);
  return next;
}

/** inactive = Gateway hat SSE abgeschaltet — kein EventSource. */
type TerminalSseUi = "inactive" | LiveStreamConnectionState;

export function LiveTerminalClient({
  initial,
  initialLoadError = null,
  symbolOptions,
  liveTerminalMeta = null,
  executionVm = null,
}: Props) {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const diagnostic = searchParams.get("diagnostic") === "1";
  const [state, setState] = useState<LiveStateResponse>(initial);
  const [symbol, setSymbol] = useState(initial.symbol);
  const [tf, setTf] = useState(normTf(initial.timeframe));
  const [showDrawings, setShowDrawings] = useState(true);
  const [showNews, setShowNews] = useState(true);
  const [frozen, setFrozen] = useState(false);
  const [sseConnection, setSseConnection] = useState<TerminalSseUi>(() =>
    liveTerminalMeta?.sseEnabled === false ? "inactive" : "connecting",
  );
  const [backfilling, setBackfilling] = useState(false);
  const [streamStale, setStreamStale] = useState(false);
  const lastPingAtRef = useRef<number>(Date.now());
  const [fetchErr, setFetchErr] = useState<string | null>(initialLoadError);
  const pollEverySec = Math.max(
    1,
    Math.round(publicEnv.livePollIntervalMs / 1000),
  );
  const ssePingStaleMs = Math.max(
    45_000,
    (liveTerminalMeta?.ssePingSec ?? publicEnv.liveSsePingSec) * 3000,
  );

  const reload = useCallback(async () => {
    try {
      const s = await fetchLiveState({
        symbol,
        timeframe: tf,
        limit: 500,
      });
      setState(s);
      setFetchErr(null);
    } catch (e) {
      setFetchErr(
        e instanceof Error ? e.message : t("live.terminal.reloadFailed"),
      );
    }
  }, [symbol, tf, t]);

  useEffect(() => {
    if (frozen || sseConnection !== "open") {
      setStreamStale(false);
      return;
    }
    const tick = () => {
      if (Date.now() - lastPingAtRef.current > ssePingStaleMs) {
        setStreamStale(true);
      }
    };
    const id = window.setInterval(tick, 10_000);
    tick();
    return () => window.clearInterval(id);
  }, [frozen, sseConnection, ssePingStaleMs]);

  useEffect(() => {
    if (liveTerminalMeta?.sseEnabled === false) {
      setSseConnection("inactive");
    }
  }, [liveTerminalMeta?.sseEnabled]);

  useEffect(() => {
    if (frozen) {
      return;
    }
    if (liveTerminalMeta?.sseEnabled === false) {
      return;
    }
    const debounced: {
      current: ReturnType<typeof globalThis.setTimeout> | null;
    } = { current: null };
    const scheduleCoalescedReload = () => {
      if (debounced.current != null) globalThis.clearTimeout(debounced.current);
      debounced.current = globalThis.setTimeout(() => {
        debounced.current = null;
        void reload();
      }, 650);
    };

    let ctrl: ReturnType<typeof startManagedLiveEventSource> | null = null;
    try {
      ctrl = startManagedLiveEventSource({
        symbol,
        timeframe: tf,
        onConnectionState: (s) => {
          if (s === "open") setSseConnection("open");
          else if (s === "reconnecting") setSseConnection("reconnecting");
          else if (s === "given_up") setSseConnection("given_up");
          else setSseConnection("connecting");
        },
        onGiveUp: () => {
          setSseConnection("given_up");
        },
        onConnectionOpen: () => {
          lastPingAtRef.current = Date.now();
          setStreamStale(false);
          setBackfilling(true);
          void reload().finally(() => setBackfilling(false));
        },
        handlers: {
          onCandle: (raw) => {
            const bar = raw as LiveCandle;
            if (
              bar &&
              typeof bar.time_s === "number" &&
              typeof bar.close === "number"
            ) {
              setState((s) => ({ ...s, candles: mergeCandle(s.candles, bar) }));
              scheduleCoalescedReload();
            }
          },
          onSignal: (raw) => {
            setState((s) => {
              const nextSig = mergeLatestSignal(s.latest_signal, raw);
              if (nextSig === s.latest_signal) return s;
              return { ...s, latest_signal: nextSig };
            });
          },
          onDrawing: () => {
            scheduleCoalescedReload();
          },
          onNews: () => {
            scheduleCoalescedReload();
          },
          onPaper: () => {
            scheduleCoalescedReload();
          },
          onPing: () => {
            lastPingAtRef.current = Date.now();
            setStreamStale(false);
          },
          onError: () => {},
        },
      });
    } catch {
      setSseConnection("reconnecting");
    }
    return () => {
      if (debounced.current != null) globalThis.clearTimeout(debounced.current);
      ctrl?.close();
    };
  }, [symbol, tf, frozen, reload, liveTerminalMeta?.sseEnabled]);

  useEffect(() => {
    if (frozen || sseConnection === "open") return;
    const id = window.setInterval(() => {
      void reload();
    }, publicEnv.livePollIntervalMs);
    return () => window.clearInterval(id);
  }, [frozen, sseConnection, reload]);

  useEffect(() => {
    if (frozen) return;
    void reload();
  }, [tf, frozen, reload]);

  const drawings = useMemo(
    () => state.latest_drawings ?? [],
    [state.latest_drawings],
  );
  const news = useMemo(() => state.latest_news ?? [], [state.latest_news]);

  const fetchProductMessage = useMemo(() => {
    if (!fetchErr) return null;
    const errObj = new Error(fetchErr);
    const base = buildProductMessageFromFetchError(errObj, t);
    return {
      ...base,
      areaLabel: t("live.terminal.fetchIssueLead"),
      userAction: `${base.userAction} ${t("live.terminal.reconnectHint")}`.trim(),
    };
  }, [fetchErr, t]);

  const streamPhase = useMemo(() => {
    if (frozen) return "frozen" as const;
    if (sseConnection === "inactive") return "sse_off" as const;
    if (backfilling) return "backfilling" as const;
    if (sseConnection === "given_up") return "sse_gave_up" as const;
    if (sseConnection === "reconnecting") return "reconnecting" as const;
    if (sseConnection === "connecting") return "connecting" as const;
    if (sseConnection === "open" && streamStale) return "stale" as const;
    if (sseConnection === "open") return "live" as const;
    return "poll" as const;
  }, [frozen, backfilling, sseConnection, streamStale]);

  const streamStatusLabel =
    streamPhase === "frozen"
      ? t("live.terminal.hintFrozen")
      : streamPhase === "sse_off"
        ? t("live.terminal.streamSseOff", { seconds: pollEverySec })
        : streamPhase === "backfilling"
          ? t("live.terminal.streamBackfilling")
          : streamPhase === "sse_gave_up"
            ? t("live.terminal.streamSseGaveUp", { seconds: pollEverySec })
            : streamPhase === "reconnecting"
              ? t("live.terminal.streamReconnecting")
              : streamPhase === "connecting"
                ? t("live.terminal.streamConnecting")
                : streamPhase === "stale"
                  ? t("live.terminal.streamStale", { seconds: pollEverySec })
                  : streamPhase === "live"
                    ? t("live.terminal.streamLive")
                    : t("live.terminal.streamPoll", { seconds: pollEverySec });

  const mf = state.market_freshness ?? null;
  const freshnessLabelKey =
    mf == null
      ? null
      : (
          {
            live: "live.terminal.freshnessLive",
            delayed: "live.terminal.freshnessDelayed",
            stale: "live.terminal.freshnessStale",
            dead: "live.terminal.freshnessDead",
            no_candles: "live.terminal.freshnessNoCandles",
            unknown_timeframe: "live.terminal.freshnessUnknownTf",
          } as const
        )[mf.status];
  /** Nur kritische Marktlücken — leichte Verzögerung steht in der Live-Datenlage-Leiste. */
  const showFreshnessBanner =
    mf != null &&
    (mf.status === "dead" ||
      mf.status === "no_candles" ||
      mf.status === "unknown_timeframe");
  const candleDiag =
    diagnostic && mf?.candle
      ? t("live.terminal.freshnessDiagCandle", {
          barLagS: Math.round(mf.candle.bar_lag_ms / 1000),
          ingestS: Math.round(mf.candle.ingest_age_ms / 1000),
        })
      : null;
  const tickerDiag =
    diagnostic && mf?.ticker
      ? t("live.terminal.freshnessDiagTicker", {
          ingestS: Math.round(mf.ticker.ingest_age_ms / 1000),
        })
      : null;

  const terminalSurfaceDiag = useMemo(
    () =>
      resolveLiveTerminalSurfaceDiagnostic({
        fetchErr,
        candleCount: state.candles.length,
        streamPhase,
        marketFreshness: mf,
        symbol,
        timeframe: tf,
        healthDb: state.health.db,
        healthRedis: state.health.redis,
        sseEnabled: liveTerminalMeta?.sseEnabled,
      }),
    [
      fetchErr,
      state.candles.length,
      streamPhase,
      mf,
      symbol,
      tf,
      state.health.db,
      state.health.redis,
      liveTerminalMeta?.sseEnabled,
    ],
  );

  const { streamStabilityKey, streamStabilityVars } = useMemo(() => {
    const sec = pollEverySec;
    switch (streamPhase) {
      case "live":
        return {
          streamStabilityKey: "live.terminal.streamLive" as const,
          streamStabilityVars: undefined,
        };
      case "frozen":
        return {
          streamStabilityKey: "live.terminal.hintFrozen" as const,
          streamStabilityVars: undefined,
        };
      case "sse_off":
        return {
          streamStabilityKey: "live.terminal.streamSseOff" as const,
          streamStabilityVars: { seconds: sec },
        };
      case "backfilling":
        return {
          streamStabilityKey: "live.terminal.streamBackfilling" as const,
          streamStabilityVars: undefined,
        };
      case "sse_gave_up":
        return {
          streamStabilityKey: "live.terminal.streamSseGaveUp" as const,
          streamStabilityVars: { seconds: sec },
        };
      case "reconnecting":
        return {
          streamStabilityKey: "live.terminal.streamReconnecting" as const,
          streamStabilityVars: undefined,
        };
      case "connecting":
        return {
          streamStabilityKey: "live.terminal.streamConnecting" as const,
          streamStabilityVars: undefined,
        };
      case "stale":
        return {
          streamStabilityKey: "live.terminal.streamStale" as const,
          streamStabilityVars: { seconds: sec },
        };
      case "poll":
        return {
          streamStabilityKey: "live.terminal.streamPoll" as const,
          streamStabilityVars: { seconds: sec },
        };
      default:
        return { streamStabilityKey: null, streamStabilityVars: undefined };
    }
  }, [streamPhase, pollEverySec]);

  const terminalSituationModel = useMemo(
    () =>
      buildLiveDataSurfaceModelFromLiveState({
        live: state,
        executionVm,
        executionModeLabel: null,
        fetchError: Boolean(fetchErr),
        loading: false,
        candleCount: state.candles.length,
        surfaceKind: "terminal",
        streamStabilityKey,
        streamStabilityVars,
      }),
    [
      state,
      executionVm,
      fetchErr,
      state.candles.length,
      streamStabilityKey,
      streamStabilityVars,
    ],
  );

  return (
    <div>
      <DemoDataNoticeBanner notice={state.demo_data_notice} />
      <LiveDataSituationBar model={terminalSituationModel} />
      {fetchErr && fetchProductMessage ? (
        <ProductMessageCard
          message={fetchProductMessage}
          showTechnical={diagnostic}
          t={t}
          className="live-terminal-fetch-issue"
        />
      ) : null}
      <header
        className="toolbar live-terminal-toolbar"
        style={{ marginBottom: 8 }}
      >
        <div className="live-terminal-toolbar__row live-terminal-toolbar__row--primary">
          <strong>{t("live.terminal.toolbarTitle")}</strong>
          <HelpHint
            briefKey="help.liveTerminal.brief"
            detailKey="help.liveTerminal.detail"
          />
          <StatusPillLink href={consolePath("ops")}>
            {t("live.terminal.toOps")}
          </StatusPillLink>
          <StatusPillLink href={consolePath("signals")}>
            {t("console.nav.signals")}
          </StatusPillLink>
          <StatusPillLink href={consolePath("health")}>
            {t("console.nav.health")}
          </StatusPillLink>
          <StatusPillLink href={consolePath("diagnostics")}>
            {t("console.nav.diagnostics")}
          </StatusPillLink>
          <StatusPillLink href={consolePath("live-broker")}>
            {t("console.nav.live_broker")}
          </StatusPillLink>
        </div>
        <div className="live-terminal-toolbar__row live-terminal-toolbar__row--toggles">
          {symbolOptions.map((item) => (
            <button
              key={item}
              type="button"
              className={symbol === item ? "active" : ""}
              onClick={() => setSymbol(item)}
            >
              {item}
            </button>
          ))}
          {TFS.map((tfOpt) => (
            <button
              key={tfOpt}
              type="button"
              className={normTf(tf) === normTf(tfOpt) ? "active" : ""}
              onClick={() => setTf(normTf(tfOpt))}
            >
              {tfOpt}
            </button>
          ))}
          <button
            type="button"
            className={showDrawings ? "active" : ""}
            onClick={() => setShowDrawings((v) => !v)}
          >
            {t("live.terminal.drawings")}
          </button>
          <button
            type="button"
            className={showNews ? "active" : ""}
            onClick={() => setShowNews((v) => !v)}
          >
            {t("live.terminal.newsMarkers")}
          </button>
          <button
            type="button"
            className={frozen ? "active" : ""}
            onClick={() => setFrozen((f) => !f)}
          >
            {frozen ? t("live.terminal.resume") : t("live.terminal.freeze")}
          </button>
        </div>
        <div
          className="live-terminal-toolbar__row live-terminal-status-strip"
          aria-live="polite"
        >
          <span className="status-pill">{symbol}</span>
          <span className="status-pill">
            {state.latest_signal?.market_family ??
              t("live.terminal.familyDash")}
          </span>
          <span
            className={`status-pill ${streamPillVariant(streamPhase)}`}
            title={
              diagnostic
                ? `sse=${sseConnection} phase=${streamPhase} poll=${pollEverySec}s meta=${liveTerminalMeta?.sseEnabled === null ? "?" : String(liveTerminalMeta?.sseEnabled)}`
                : undefined
            }
          >
            {t("live.terminal.streamLabel")}: {streamStatusLabel}
          </span>
          <button
            type="button"
            className="public-btn ghost live-terminal-reload-btn"
            onClick={() => void reload()}
            aria-label={t("live.terminal.btnReloadAria")}
          >
            {t("live.terminal.btnReload")}
          </button>
        </div>
        <details className="live-terminal-tech-details muted small">
          <summary>{t("live.terminal.techDetailsSummary")}</summary>
          <div className="live-terminal-tech-details__body">
            <span
              className={`status-pill ${healthPillVariant(state.health.db)}`}
            >
              {t("live.terminal.dbLabel")} {state.health.db}
            </span>
            <span
              className={`status-pill ${healthPillVariant(state.health.redis)}`}
            >
              {t("live.terminal.redisLabel")} {state.health.redis}
            </span>
            {freshnessLabelKey && mf ? (
              <span
                className={`status-pill ${freshnessPillVariant(mf.status)}`}
                title={
                  diagnostic
                    ? [candleDiag, tickerDiag].filter(Boolean).join(" · ") ||
                      undefined
                    : undefined
                }
              >
                {t(freshnessLabelKey)}
              </span>
            ) : null}
          </div>
        </details>
      </header>
      {!fetchErr && !frozen ? (
        streamPhase === "sse_off" ? (
          <p
            className="muted small live-terminal-transport-note"
            role="status"
            style={{ margin: "4px 0 8px" }}
          >
            {t("live.terminal.transportHintSseOff", {
              seconds: pollEverySec,
            })}
          </p>
        ) : streamPhase === "sse_gave_up" ? (
          <p
            className="muted small live-terminal-transport-note"
            role="status"
            style={{ margin: "4px 0 8px" }}
          >
            {t("live.terminal.transportHintSseGaveUp", {
              seconds: pollEverySec,
            })}
          </p>
        ) : streamPhase === "poll" ||
          streamPhase === "connecting" ||
          streamPhase === "reconnecting" ? (
          <p
            className="muted small live-terminal-transport-note"
            role="status"
            style={{ margin: "4px 0 8px" }}
          >
            {t("live.terminal.transportHintPolling", {
              seconds: pollEverySec,
            })}
          </p>
        ) : null
      ) : null}
      {showFreshnessBanner && freshnessLabelKey && mf ? (
        <div
          className={`live-terminal-banner ${freshnessBannerModifier(mf.status)}`}
          role={freshnessBannerRole(mf.status)}
        >
          <strong>{t("live.terminal.freshnessBannerLead")}</strong>{" "}
          {t(freshnessLabelKey)}
          {candleDiag ? (
            <span
              className="muted small"
              style={{ display: "block", marginTop: 4 }}
            >
              {candleDiag}
              {tickerDiag ? ` · ${tickerDiag}` : ""}
            </span>
          ) : null}
        </div>
      ) : null}
      {state.empty_state && state.message ? (
        <div
          className="live-terminal-banner live-terminal-banner--info"
          role="status"
        >
          <strong>{t("live.terminal.emptyStateBanner")}</strong> {state.message}
          {state.next_step ? (
            <span className="muted"> — {state.next_step}</span>
          ) : null}
        </div>
      ) : null}
      {!fetchErr && state.candles.length === 0 ? (
        <EmptyStateHelp
          titleKey="help.liveEmpty.title"
          bodyKey="help.liveEmpty.body"
          stepKeys={[
            "help.liveEmpty.s1",
            "help.liveEmpty.s2",
            "help.liveEmpty.s3",
          ]}
        />
      ) : null}
      {terminalSurfaceDiag ? (
        <SurfaceDiagnosticCard model={terminalSurfaceDiag} />
      ) : null}
      <LiveDataLineagePanel
        segments={state.data_lineage}
        onlineDriftEffective={state.online_drift?.effective_action}
        onlineDriftComputedAt={state.online_drift?.computed_at ?? undefined}
      />
      <div className="terminal-layout">
        <div className="terminal-main">
          <p className="muted small live-terminal-chart-caption">
            {t("live.terminal.chartCaption")}
          </p>
          <ChartPanel
            candles={state.candles}
            drawings={drawings}
            news={news as LiveNewsItem[]}
            showDrawings={showDrawings}
            showNewsMarkers={showNews}
            strategyContext={{
              signal: state.latest_signal,
              markPrice: state.paper_state?.mark_price ?? null,
              tickerLast: state.market_freshness?.ticker?.last_pr ?? null,
            }}
          />
          <PaperPanel paper={state.paper_state} />
        </div>
        <div className="terminal-side">
          <SignalPanel signal={state.latest_signal} />
          <MicrostructurePanel feature={state.latest_feature} />
          <NewsPanel items={news as LiveNewsItem[]} compact />
        </div>
      </div>
    </div>
  );
}
