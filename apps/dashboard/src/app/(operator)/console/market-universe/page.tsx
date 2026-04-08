import Link from "next/link";

import { ConsoleLiveMarketChartSection } from "@/components/console/ConsoleLiveMarketChartSection";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { HealthSnapshotLoadNotice } from "@/components/console/HealthSnapshotLoadNotice";
import { Header } from "@/components/layout/Header";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import { MarketCapabilityMatrixTable } from "@/components/market/MarketCapabilityMatrixTable";
import {
  fetchMarketUniverseStatus,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { buildLiveDataSurfaceModelFromHealth } from "@/lib/live-data-surface-model";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { normalizeChartTimeframe } from "@/lib/chart-prefs";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { publicEnv } from "@/lib/env";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { resolveTradeSymbol } from "@/lib/resolve-trade-symbol";

export const dynamic = "force-dynamic";

function first(sp: ConsoleSearchParams, key: string): string | undefined {
  const v = sp[key];
  return Array.isArray(v) ? v[0] : v;
}

function boolLabel(
  value: boolean,
  t: (key: string, vars?: Record<string, string | number | boolean>) => string,
): string {
  return value ? t("account.yes") : t("account.no");
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

export default async function MarketUniversePage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let data: import("@/lib/types").MarketUniverseStatusResponse | null = null;
  let error: string | null = null;

  try {
    data = await fetchMarketUniverseStatus();
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const { health, error: healthLoadError } =
    await fetchSystemHealthBestEffort();
  const executionVm = executionPathFromSystemHealth(health);
  const muHealthModel = buildLiveDataSurfaceModelFromHealth({
    health,
    surfaceKind: "market_universe_meta",
  });

  const chartPrefs = await readConsoleChartPrefs();
  const muChartSymbol = resolveTradeSymbol(
    first(sp, "symbol") ?? chartPrefs.symbol,
  );
  const muChartTf =
    normalizeChartTimeframe(first(sp, "timeframe")) ??
    chartPrefs.timeframe ??
    normalizeChartTimeframe(publicEnv.defaultTimeframe) ??
    "5m";
  const muChartNav: Record<string, string> = {
    symbol: muChartSymbol,
    timeframe: muChartTf,
  };

  return (
    <>
      <Header
        title={t("pages.marketUniverse.title")}
        subtitle={t("pages.marketUniverse.subtitle")}
      />
      <p className="muted small">
        {t("pages.marketUniverse.relatedLead")}{" "}
        <Link href={consolePath("capabilities")}>
          {t("console.nav.capabilities")}
        </Link>
        {" · "}
        <Link href={consolePath("terminal")}>{t("console.nav.terminal")}</Link>
        {" · "}
        <Link href={consolePath("signals")}>{t("console.nav.signals")}</Link>
        {" · "}
        <Link href={consolePath("ops")}>{t("console.nav.ops")}</Link>
      </p>
      {muHealthModel ? <LiveDataSituationBar model={muHealthModel} /> : null}
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
      </div>
      {!error && !data ? (
        <div className="panel" role="status">
          <h2>{t("pages.marketUniverse.unavailableTitle")}</h2>
          <p className="muted">{t("pages.marketUniverse.unavailableBody")}</p>
          <p className="muted small">
            <Link href={consolePath("health")}>{t("console.nav.health")}</Link>
            {" · "}
            <a
              href="/api/dashboard/edge-status"
              target="_blank"
              rel="noreferrer"
            >
              {t("live.terminal.edgeStatusLink")}
            </a>
          </p>
        </div>
      ) : null}
      {!data ? null : (
        <>
          <div className="panel">
            <h2>{t("pages.marketUniverse.snapshotTitle")}</h2>
            <div className="signal-grid">
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelSchema")}
                </span>
                <div className="mono-small">{data.schema_version}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelSnapshot")}
                </span>
                <div className="mono-small">
                  {data.snapshot?.snapshot_id ?? "—"}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelStatus")}
                </span>
                <div>
                  {data.snapshot?.status ??
                    t("pages.marketUniverse.statusMissing")}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelSource")}
                </span>
                <div>{data.snapshot?.source_service ?? "—"}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelRefreshDone")}
                </span>
                <div>{fmtTs(data.snapshot?.fetch_completed_ts_ms)}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelFamiliesUpdated")}
                </span>
                <div>{data.snapshot?.refreshed_families.join(", ") || "—"}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelCategories")}
                </span>
                <div>{data.summary.category_count}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelInstruments")}
                </span>
                <div>{data.summary.instrument_count}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelAnalyticsEligibleCat")}
                </span>
                <div>{data.summary.analytics_eligible_category_count}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelLiveEnabledCat")}
                </span>
                <div>{data.summary.live_execution_enabled_category_count}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelExecutionDisabledCat")}
                </span>
                <div>{data.summary.execution_disabled_category_count}</div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelLiveEnabledInstr")}
                </span>
                <div>
                  {data.summary.live_execution_enabled_instrument_count}
                </div>
              </div>
            </div>
            {data.snapshot?.warnings?.length ? (
              <>
                <h3>{t("pages.marketUniverse.warningsHeading")}</h3>
                <ul className="news-list">
                  {data.snapshot.warnings.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {data.snapshot?.errors?.length ? (
              <>
                <h3>{t("pages.marketUniverse.errorsHeading")}</h3>
                <ul className="news-list">
                  {data.snapshot.errors.map((item) => (
                    <li key={item} className="operator-warn">
                      {item}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>

          <ConsoleLiveMarketChartSection
            pathname={consolePath("market-universe")}
            urlParams={muChartNav}
            chartSymbol={muChartSymbol}
            chartTimeframe={muChartTf}
            executionVm={executionVm}
            executionModeLabel={health?.execution.execution_mode ?? null}
            symbolOptions={
              data.configuration.watchlist_symbols.length > 0
                ? data.configuration.watchlist_symbols
                : data.configuration.universe_symbols.slice(0, 48)
            }
            panelTitleKey="pages.marketUniverse.chartPanelTitle"
            showLiveDataSituationBar={false}
          />

          <div className="panel">
            <h2>{t("pages.marketUniverse.configuredTitle")}</h2>
            <div className="signal-grid">
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelFamilies")}
                </span>
                <div>
                  {data.configuration.market_families.join(", ") || "—"}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelUniverseSymbols")}
                </span>
                <div className="mono-small">
                  {data.configuration.universe_symbols.join(", ") || "—"}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelWatchlist")}
                </span>
                <div className="mono-small">
                  {data.configuration.watchlist_symbols.join(", ") || "—"}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelFeatureScopeTfs")}
                </span>
                <div>
                  {data.configuration.feature_scope.timeframes.join(", ") ||
                    "—"}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelLiveFamilies")}
                </span>
                <div>
                  {data.configuration.live_allowlists.market_families.join(
                    ", ",
                  ) || "—"}
                </div>
              </div>
              <div>
                <span className="label">
                  {t("pages.marketUniverse.labelLiveProductTypes")}
                </span>
                <div>
                  {data.configuration.live_allowlists.product_types.join(
                    ", ",
                  ) || "—"}
                </div>
              </div>
            </div>
          </div>

          <div className="panel">
            <h2>{t("pages.marketUniverse.matrixHeading")}</h2>
            <MarketCapabilityMatrixTable categories={data.categories} />
          </div>

          <div className="panel">
            <h2>{t("pages.marketUniverse.registryTitle")}</h2>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("pages.marketUniverse.thInstrument")}</th>
                    <th>{t("pages.marketUniverse.thFamily")}</th>
                    <th>{t("pages.marketUniverse.thProductMode")}</th>
                    <th>{t("pages.marketUniverse.thCoins")}</th>
                    <th>{t("pages.marketUniverse.thInventory")}</th>
                    <th>{t("pages.marketUniverse.thAnalytics")}</th>
                    <th>{t("pages.marketUniverse.thPaperShadow")}</th>
                    <th>{t("pages.marketUniverse.thLive")}</th>
                    <th>{t("pages.marketUniverse.thLeverage")}</th>
                    <th>{t("pages.marketUniverse.thShorting")}</th>
                    <th>{t("pages.marketUniverse.thTradeSubscribe")}</th>
                    <th>{t("pages.marketUniverse.thMetadata")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.instruments.map((item) => (
                    <tr key={item.canonical_instrument_id}>
                      <td>
                        <div>{item.symbol}</div>
                        <div className="mono-small">
                          {item.canonical_instrument_id}
                        </div>
                      </td>
                      <td>{item.market_family}</td>
                      <td>{item.product_type ?? item.margin_account_mode}</td>
                      <td>
                        {[item.base_coin, item.quote_coin, item.settle_coin]
                          .filter(Boolean)
                          .join(" / ") || "—"}
                      </td>
                      <td>{boolLabel(item.inventory_visible, t)}</td>
                      <td>{boolLabel(item.analytics_eligible, t)}</td>
                      <td>{boolLabel(item.paper_shadow_eligible, t)}</td>
                      <td>{boolLabel(item.live_execution_enabled, t)}</td>
                      <td>{boolLabel(item.supports_leverage, t)}</td>
                      <td>{boolLabel(item.supports_shorting, t)}</td>
                      <td>
                        {boolLabel(item.trading_enabled, t)} /{" "}
                        {boolLabel(item.subscribe_enabled, t)}
                      </td>
                      <td className="mono-small">
                        {item.metadata_source}
                        <br />
                        {t("pages.marketUniverse.metaVerifiedTpl", {
                          value: boolLabel(item.metadata_verified, t),
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
