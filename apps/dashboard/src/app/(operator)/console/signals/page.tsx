import Link from "next/link";

import { ConsoleLiveMarketChartSection } from "@/components/console/ConsoleLiveMarketChartSection";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import { ConsoleSurfaceNotice } from "@/components/console/ConsoleSurfaceNotice";
import { HealthSnapshotLoadNotice } from "@/components/console/HealthSnapshotLoadNotice";
import { Header } from "@/components/layout/Header";
import { SignalsTable } from "@/components/tables/SignalsTable";
import {
  fetchSignalsFacets,
  fetchSignalsRecent,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { buildLiveDataSurfaceModelFromSignalsRead } from "@/lib/live-data-surface-model";
import {
  resolveConsoleChartSymbolOptions,
  resolveConsoleChartSymbolTimeframe,
} from "@/lib/console-chart-context";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  firstSearchParam,
} from "@/lib/console-params";
import { consoleHref, pickTruthyQueryFields } from "@/lib/console-url-params";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { publicEnv } from "@/lib/env";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { SignalsFacetsResponse, SignalsRecentResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type SP = Record<string, string | string[] | undefined>;

/** Reihenfolge: Defaults zuerst, dann Facet-Werte ohne Duplikat (case-sensitiver Key). */
function mergeOptionList(
  preferred: string[],
  fromFacets: string[] | undefined,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of [...preferred, ...(fromFacets ?? [])]) {
    const x = raw.trim();
    if (!x) continue;
    const key = x.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(x);
  }
  return out;
}

function timeframeLinkActive(
  urlTf: string | undefined,
  optionTf: string,
): boolean {
  if (!urlTf) return false;
  return urlTf.trim().toLowerCase() === optionTf.trim().toLowerCase();
}

function directionLinkActive(
  urlDir: string | undefined,
  optionDir: string,
): boolean {
  if (!urlDir) return false;
  return urlDir.trim().toLowerCase() === optionDir.trim().toLowerCase();
}

export default async function SignalsPage({
  searchParams,
}: {
  searchParams: SP | Promise<SP>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const timeframe = firstSearchParam(sp, "timeframe");
  const direction = firstSearchParam(sp, "direction");
  const symbol = firstSearchParam(sp, "symbol");
  const marketFamily = firstSearchParam(sp, "market_family");
  const playbookFamily = firstSearchParam(sp, "playbook_family");
  const playbookId = firstSearchParam(sp, "playbook_id");
  const tradeAction = firstSearchParam(sp, "trade_action");
  const metaLane = firstSearchParam(sp, "meta_trade_lane");
  const regimeState = firstSearchParam(sp, "regime_state");
  const specialistRouter = firstSearchParam(sp, "specialist_router_id");
  const exitFamily = firstSearchParam(sp, "exit_family");
  const decisionState = firstSearchParam(sp, "decision_state");
  const strategyName = firstSearchParam(sp, "strategy_name");
  const signalClass = firstSearchParam(sp, "signal_class");
  const signalRegistryKey = firstSearchParam(sp, "signal_registry_key");
  const minStrengthRaw = firstSearchParam(sp, "min_strength");
  const minStrength =
    minStrengthRaw !== undefined ? Number(minStrengthRaw) : undefined;

  const chartPrefs = await readConsoleChartPrefs();
  const { health, error: healthLoadError } =
    await fetchSystemHealthBestEffort();
  const executionVm = executionPathFromSystemHealth(health);
  const {
    chartSymbol: effectiveChartSymbol,
    chartTimeframe: effectiveChartTf,
  } = resolveConsoleChartSymbolTimeframe({
    urlSymbol: symbol,
    urlTimeframe: timeframe,
    persistedSymbol: chartPrefs.symbol,
    persistedTimeframe: chartPrefs.timeframe,
    defaultSymbol: publicEnv.defaultSymbol,
    defaultTimeframe: publicEnv.defaultTimeframe,
  });

  let data: SignalsRecentResponse = {
    items: [],
    limit: 50,
    status: "ok",
    message: null,
    empty_state: true,
    degradation_reason: null,
    next_step: null,
    filters_active: false,
  };
  let facets: SignalsFacetsResponse | null = null;
  let error: string | null = null;
  let facetsErr: string | null = null;
  try {
    [data, facets] = await Promise.all([
      fetchSignalsRecent({
        symbol: symbol?.trim() || undefined,
        timeframe,
        direction,
        min_strength: Number.isFinite(minStrength) ? minStrength : undefined,
        market_family: marketFamily,
        playbook_family: playbookFamily,
        playbook_id: playbookId,
        trade_action: tradeAction,
        meta_trade_lane: metaLane,
        regime_state: regimeState,
        specialist_router_id: specialistRouter,
        exit_family: exitFamily,
        decision_state: decisionState,
        strategy_name: strategyName,
        signal_class: signalClass,
        signal_registry_key: signalRegistryKey,
        limit: 120,
      }),
      fetchSignalsFacets({ lookback_rows: 4000 }).catch((e) => {
        facetsErr = e instanceof Error ? e.message : t("errors.facetsFallback");
        return null;
      }),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const baseQs: Record<string, string | undefined> = {
    timeframe,
    direction,
    symbol,
    market_family: marketFamily,
    playbook_family: playbookFamily,
    playbook_id: playbookId,
    trade_action: tradeAction,
    meta_trade_lane: metaLane,
    regime_state: regimeState,
    specialist_router_id: specialistRouter,
    exit_family: exitFamily,
    decision_state: decisionState,
    strategy_name: strategyName,
    signal_class: signalClass,
    signal_registry_key: signalRegistryKey,
    min_strength: minStrengthRaw,
  };

  const href = (extra: Record<string, string | undefined | null>) =>
    consoleHref(consolePath("signals"), baseQs, extra);

  const chartNavParams = pickTruthyQueryFields(baseQs);

  const tfOptions = mergeOptionList(
    ["1m", "5m", "15m", "1h", "4h"],
    facets?.timeframes,
  );
  const directionOptions = mergeOptionList(
    ["long", "short", "neutral"],
    facets?.directions,
  );
  const tradeActionOptions = mergeOptionList(
    ["allow_trade", "do_not_trade"],
    facets?.trade_actions,
  );

  return (
    <>
      <Header
        title={t("pages.signals.title")}
        subtitle={t("pages.signals.subtitle")}
        helpBriefKey="help.signals.pageBrief"
        helpDetailKey="help.signals.pageDetail"
      />
      <p className="muted small">
        {t("console.quickLinksLead")}{" "}
        <Link href={consolePath("terminal")}>{t("console.nav.terminal")}</Link>
        {" · "}
        <Link href={consolePath("no-trade")}>{t("console.nav.no_trade")}</Link>
        {" · "}
        <Link href={consolePath("ops")}>{t("console.nav.ops")}</Link>
        {" · "}
        <Link href={consolePath("market-universe")}>
          {t("console.nav.market_universe")}
        </Link>
      </p>
      <LiveDataSituationBar
        model={buildLiveDataSurfaceModelFromSignalsRead({
          data,
          executionVm,
          fetchFailed: Boolean(error),
        })}
      />
      <div
        className="console-page-notice-stack"
        aria-label={t("console.pageNoticesGroupAria")}
      >
        <HealthSnapshotLoadNotice
          error={healthLoadError}
          diagnostic={diagnostic}
          t={t}
        />
        <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
        <PanelDataIssue err={facetsErr} diagnostic={diagnostic} t={t} />
      </div>
      <ConsoleLiveMarketChartSection
        pathname={consolePath("signals")}
        urlParams={chartNavParams}
        chartSymbol={effectiveChartSymbol}
        chartTimeframe={effectiveChartTf}
        symbolOptions={resolveConsoleChartSymbolOptions({
          facetSymbols: facets?.symbols,
          watchlist: publicEnv.watchlistSymbols,
          chartSymbol: effectiveChartSymbol,
        })}
        executionVm={executionVm}
        executionModeLabel={health?.execution.execution_mode ?? null}
        panelTitleKey="pages.signals.chartPanelTitle"
        showLiveDataSituationBar={false}
      />
      <div className="panel">
        <h2>{t("pages.signals.filters.universeTitle")}</h2>
        <div className="signal-grid">
          <div>
            <span className="label">
              {t("pages.signals.filters.observedSymbols")}
            </span>
            <div>{facets?.symbols.length ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.signals.filters.marketFamilies")}
            </span>
            <div>{facets?.market_families.length ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.signals.filters.playbookFamilies")}
            </span>
            <div>{facets?.playbook_families.length ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.signals.filters.specialistRouters")}
            </span>
            <div>{facets?.specialist_routers.length ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.signals.filters.exitFamilies")}
            </span>
            <div>{facets?.exit_families.length ?? "—"}</div>
          </div>
          <div>
            <span
              className="label"
              title={t("pages.signals.filters.hintFacetCounts")}
            >
              {t("pages.signals.filters.facetCountTimeframes")}
            </span>
            <div>{facets?.timeframes.length ?? "—"}</div>
          </div>
          <div>
            <span
              className="label"
              title={t("pages.signals.filters.hintFacetCounts")}
            >
              {t("pages.signals.filters.facetCountDecisionStates")}
            </span>
            <div>{facets?.decision_states.length ?? "—"}</div>
          </div>
          <div>
            <span
              className="label"
              title={t("pages.signals.filters.hintFacetCounts")}
            >
              {t("pages.signals.filters.facetCountStrategies")}
            </span>
            <div>{facets?.strategy_names.length ?? "—"}</div>
          </div>
          <div>
            <span className="label">
              {t("pages.signals.filters.activeScope")}
            </span>
            <div className="mono-small">
              {t("pages.signals.filters.activeScopeValues", {
                symbol: symbol ?? t("pages.signals.filters.all"),
                family: marketFamily ?? t("pages.signals.filters.allFamilies"),
                tf: timeframe ?? t("pages.signals.filters.allTf"),
              })}
            </div>
          </div>
        </div>
        {facets &&
        facets.message &&
        (facets.empty_state || facets.status === "degraded") ? (
          <ConsoleSurfaceNotice
            t={t}
            variant="soft"
            titleKey="pages.signals.facetsEnvelopeTitle"
            body={facets.message}
            refreshHint={facets.next_step}
            showStateActions
            showTechnical={diagnostic && facets.degradation_reason != null}
            technical={
              facets.degradation_reason != null
                ? String(facets.degradation_reason)
                : null
            }
            diagnosticSummaryLabel={t("ui.diagnostic.summary")}
            style={{ marginTop: 12 }}
          />
        ) : null}
        {facets ? (
          <p className="muted small" style={{ marginTop: 8 }}>
            {t("pages.signals.filters.facetsMirrorNote")}
          </p>
        ) : null}
      </div>
      <div className="panel">
        <h2>{t("pages.signals.filters.instrumentTitle")}</h2>
        <div className="filter-row">
          <span className="muted" title={t("pages.signals.filters.hintSymbol")}>
            {t("pages.signals.filters.labelSymbol")}:
          </span>
          <Link
            href={href({ symbol: null })}
            className={!symbol ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.symbols ?? []).slice(0, 24).map((sym) => (
            <Link
              key={sym}
              href={href({ symbol: sym })}
              className={symbol === sym ? "active" : ""}
            >
              {sym}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintMarketFamily")}
          >
            {t("pages.signals.filters.labelMarketFamily")}:
          </span>
          <Link
            href={href({ market_family: null })}
            className={!marketFamily ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.market_families ?? []).map((mf) => (
            <Link
              key={mf}
              href={href({ market_family: mf })}
              className={marketFamily === mf ? "active" : ""}
            >
              {mf}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintPlaybookFamily")}
          >
            {t("pages.signals.filters.labelPlaybookFamily")}:
          </span>
          <Link
            href={href({ playbook_family: null })}
            className={!playbookFamily ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.playbook_families ?? []).map((pf) => (
            <Link
              key={pf}
              href={href({ playbook_family: pf })}
              className={playbookFamily === pf ? "active" : ""}
            >
              {pf}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintPlaybookIdQuick")}
          >
            {t("pages.signals.filters.labelPlaybookIdQuick")}:
          </span>
          <Link
            href={href({ playbook_id: null })}
            className={!playbookId ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.playbook_ids ?? []).slice(0, 20).map((pid) => (
            <Link
              key={pid}
              href={href({ playbook_id: pid })}
              className={playbookId === pid ? "active" : ""}
            >
              {pid}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintMetaTradeLane")}
          >
            {t("pages.signals.filters.labelMetaTradeLane")}:
          </span>
          <Link
            href={href({ meta_trade_lane: null })}
            className={!metaLane ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.meta_trade_lanes ?? []).map((lane) => (
            <Link
              key={lane}
              href={href({ meta_trade_lane: lane })}
              className={metaLane === lane ? "active" : ""}
            >
              {lane}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintRegimeState")}
          >
            {t("pages.signals.filters.labelRegimeState")}:
          </span>
          <Link
            href={href({ regime_state: null })}
            className={!regimeState ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.regime_states ?? []).map((rs) => (
            <Link
              key={rs}
              href={href({ regime_state: rs })}
              className={regimeState === rs ? "active" : ""}
            >
              {rs}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintSpecialistRouter")}
          >
            {t("pages.signals.filters.labelSpecialistRouter")}:
          </span>
          <Link
            href={href({ specialist_router_id: null })}
            className={!specialistRouter ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.specialist_routers ?? []).map((router) => (
            <Link
              key={router}
              href={href({ specialist_router_id: router })}
              className={specialistRouter === router ? "active" : ""}
            >
              {router}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintExitFamily")}
          >
            {t("pages.signals.filters.labelExitFamily")}:
          </span>
          <Link
            href={href({ exit_family: null })}
            className={!exitFamily ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.exit_families ?? []).map((exit) => (
            <Link
              key={exit}
              href={href({ exit_family: exit })}
              className={exitFamily === exit ? "active" : ""}
            >
              {exit}
            </Link>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{t("pages.signals.filters.moreFiltersTitle")}</h2>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintTimeframe")}
          >
            {t("pages.signals.filters.labelTimeframe")}:
          </span>
          {tfOptions.map((tf) => (
            <Link
              key={tf}
              href={href({ timeframe: tf })}
              className={timeframeLinkActive(timeframe, tf) ? "active" : ""}
            >
              {tf}
            </Link>
          ))}
          <Link
            href={href({ timeframe: null })}
            className={!timeframe ? "active" : ""}
          >
            {t("pages.signals.filters.allTf")}
          </Link>
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintDirection")}
          >
            {t("pages.signals.filters.labelDirection")}:
          </span>
          {directionOptions.map((d) => (
            <Link
              key={d}
              href={href({ direction: d })}
              className={directionLinkActive(direction, d) ? "active" : ""}
            >
              {d}
            </Link>
          ))}
          <Link
            href={href({ direction: null })}
            className={!direction ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintTradeAction")}
          >
            {t("pages.signals.filters.labelTradeAction")}:
          </span>
          <Link
            href={href({ trade_action: null })}
            className={!tradeAction ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {tradeActionOptions.map((ta) => (
            <Link
              key={ta}
              href={href({ trade_action: ta })}
              className={
                tradeAction?.trim().toLowerCase() === ta.trim().toLowerCase()
                  ? "active"
                  : ""
              }
            >
              {ta}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintDecisionState")}
          >
            {t("pages.signals.filters.labelDecisionState")}:
          </span>
          <Link
            href={href({ decision_state: null })}
            className={!decisionState ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.decision_states ?? []).slice(0, 24).map((ds) => (
            <Link
              key={ds}
              href={href({ decision_state: ds })}
              className={decisionState === ds ? "active" : ""}
            >
              {ds}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintStrategyName")}
          >
            {t("pages.signals.filters.labelStrategyName")}:
          </span>
          <Link
            href={href({ strategy_name: null })}
            className={!strategyName ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.strategy_names ?? []).slice(0, 20).map((sn) => (
            <Link
              key={sn}
              href={href({ strategy_name: sn })}
              className={strategyName === sn ? "active" : ""}
            >
              {sn}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintSignalClass")}
          >
            {t("pages.signals.filters.labelSignalClass")}:
          </span>
          <Link
            href={href({ signal_class: null })}
            className={!signalClass ? "active" : ""}
          >
            {t("pages.signals.filters.all")}
          </Link>
          {(facets?.signal_classes ?? []).slice(0, 16).map((sc) => (
            <Link
              key={sc}
              href={href({ signal_class: sc })}
              className={signalClass === sc ? "active" : ""}
            >
              {sc}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintMinStrength")}
          >
            {t("pages.signals.filters.labelMinStrength")}:
          </span>
          {[40, 60, 80].map((n) => (
            <Link
              key={n}
              href={href({ min_strength: String(n) })}
              className={minStrengthRaw === String(n) ? "active" : ""}
            >
              ≥{n}
            </Link>
          ))}
          <Link
            href={href({ min_strength: null })}
            className={!minStrengthRaw ? "active" : ""}
          >
            {t("pages.signals.filters.minStrengthNone")}
          </Link>
        </div>
        <form method="get" className="filter-row" style={{ marginTop: 10 }}>
          {timeframe ? (
            <input type="hidden" name="timeframe" value={timeframe} />
          ) : null}
          {direction ? (
            <input type="hidden" name="direction" value={direction} />
          ) : null}
          {symbol ? <input type="hidden" name="symbol" value={symbol} /> : null}
          {marketFamily ? (
            <input type="hidden" name="market_family" value={marketFamily} />
          ) : null}
          {playbookFamily ? (
            <input
              type="hidden"
              name="playbook_family"
              value={playbookFamily}
            />
          ) : null}
          {tradeAction ? (
            <input type="hidden" name="trade_action" value={tradeAction} />
          ) : null}
          {metaLane ? (
            <input type="hidden" name="meta_trade_lane" value={metaLane} />
          ) : null}
          {regimeState ? (
            <input type="hidden" name="regime_state" value={regimeState} />
          ) : null}
          {specialistRouter ? (
            <input
              type="hidden"
              name="specialist_router_id"
              value={specialistRouter}
            />
          ) : null}
          {exitFamily ? (
            <input type="hidden" name="exit_family" value={exitFamily} />
          ) : null}
          {decisionState ? (
            <input type="hidden" name="decision_state" value={decisionState} />
          ) : null}
          {strategyName ? (
            <input type="hidden" name="strategy_name" value={strategyName} />
          ) : null}
          {signalClass ? (
            <input type="hidden" name="signal_class" value={signalClass} />
          ) : null}
          {signalRegistryKey ? (
            <input
              type="hidden"
              name="signal_registry_key"
              value={signalRegistryKey}
            />
          ) : null}
          {minStrengthRaw ? (
            <input type="hidden" name="min_strength" value={minStrengthRaw} />
          ) : null}
          <label
            className="muted"
            htmlFor="playbook_id"
            title={t("pages.signals.filters.hintPlaybookIdExact")}
          >
            {t("pages.signals.filters.playbookIdExact")}
          </label>
          <input
            id="playbook_id"
            name="playbook_id"
            className="console-filter-input"
            defaultValue={playbookId ?? ""}
            placeholder={t("pages.signals.filters.playbookIdPlaceholder")}
            autoComplete="off"
          />
          <button type="submit" className="console-filter-submit">
            {t("pages.signals.filters.apply")}
          </button>
          {playbookId ? (
            <Link href={href({ playbook_id: null })}>
              {t("pages.signals.filters.clearPlaybookId")}
            </Link>
          ) : null}
        </form>
        {facets ? (
          <p className="muted small" style={{ marginTop: 8 }}>
            {t("pages.signals.filters.facetsWindowNote", {
              rows: facets.lookback_rows,
            })}
          </p>
        ) : null}
      </div>
      <div className="panel signals-table-wide">
        <h2>{t("pages.signals.tableSectionTitle")}</h2>
        {!error &&
        data.items.length === 0 &&
        (data.message || data.next_step) ? (
          <div
            className="console-fetch-notice console-fetch-notice--soft"
            role="status"
            style={{ marginBottom: 12 }}
          >
            <p className="console-fetch-notice__title">
              {t("pages.signals.recentEmptyTitle")}
            </p>
            {data.message ? (
              <p className="console-fetch-notice__body muted small">
                {data.message}
              </p>
            ) : null}
            {data.next_step ? (
              <p className="console-fetch-notice__refresh muted small">
                {data.next_step}
              </p>
            ) : null}
            {diagnostic && data.degradation_reason ? (
              <p className="mono-small muted">
                reason={String(data.degradation_reason)}
              </p>
            ) : null}
            {data.filters_active ? (
              <p className="muted small" style={{ marginTop: 6 }}>
                <Link href={consolePath("signals")}>
                  {t("pages.signals.clearAllFilters")}
                </Link>
              </p>
            ) : null}
          </div>
        ) : null}
        <SignalsTable items={data.items} />
      </div>
    </>
  );
}
